#!/usr/bin/env python3
"""Bounded real project chat, source change observation and fresh-VM recovery."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from lfe_repl import Bridge, Chat, FrontendError, TOOLS
from lfe_toolkit import WORKSPACE_TOOLS


class Output:
    def text(self, value):
        print(value, flush=True)

    def result(self, result, **kwargs):
        print(json.dumps({k: result[k] for k in ('status', 'revision', 'reason')}), flush=True)


class BoundedChat(Chat):
    def _response(self):
        if self.request_count >= 30:
            raise FrontendError('Workspace live test reached its 30-request ceiling.')
        print(f'Model request {self.request_count+1}/30', flush=True)
        return super()._response()

    def _tool(self, call):
        self.called.append(call['name'])
        if len(self.called) > 28:
            raise FrontendError('Workspace live test reached its 28-tool ceiling.')
        if call['name'] not in {'lfe_'+op for op in WORKSPACE_TOOLS} | {'lfe_status'}:
            raise FrontendError('Live project test allows only project workspace observations and metadata.')
        result = super()._tool(call)
        self.receipts.append({'name': call['name'], 'result': result})
        return result


def direct(c, op, **args):
    return Chat._tool(c, {'name': 'lfe_'+op, 'arguments': json.dumps(args)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    store = args.output/'store'
    if (store/'CURRENT').exists():
        parser.error('Use a fresh output directory; no workflow is replayed.')
    report = dict(status='started', request_ceiling=30, tool_ceiling=28, started_at=time.time(),
                  monetary_charges='unknown', max_admitted_workers=0)
    bridge, chat = None, None
    # Public synthetic source fixture; model tools cannot write it.
    with tempfile.TemporaryDirectory(prefix='workspace-live-fixture-', dir=ROOT/'tests') as temporary:
        project = Path(temporary)
        (project/'src').mkdir()
        (project/'docs').mkdir()
        source = project/'src'/'engine.py'
        original = 'class Engine:\n    def run(self, x):\n        return x * 2\n\ndef apply_engine(x):\n    return Engine().run(x)\n'
        source.write_text(original)
        (project/'docs'/'contract.md').write_text('# Engine contract\nEngine.run(x) returns x * 2.\n')
        relative = 'jiti/'+project.relative_to(ROOT).as_posix()
        report['fixture_root'] = relative
        prompt = (
            f'Use the new project workspace to study this public synthetic project. '
            f'Open it as id=engine-demo, root={relative}, title="Engine demo", '
            'description="Source and contract inspection". Use actual current expected_revision and preview=false. '
            'Inspect its tree. Search across files for Engine, then map Engine symbols using workspace_symbols. '
            'Read docs/contract.md by line and src/engine.py by line. '
            'Pin src/engine.py with label="Implementation" and docs/contract.md with label="Acceptance". '
            'Capture source snapshot id=baseline, then build workspace_context query="Engine". '
            'Report the actual file evidence, implementation/contract agreement, and snapshot coverage. '
            'Use only project workspace tools and lfe_status. Do not execute or import source, start any jobs, '
            'create managed functions, use generic workspace readers, or change any files. '
            'The project root persists; all project tool paths are relative to that root.')
        try:
            bridge = Bridge(store)
            chat = BoundedChat(bridge, Output(), model=args.model, tool_limit=20, timeout=60)
            chat.called, chat.receipts = [], []
            report['model'] = chat.model
            chat.turn(prompt)
            current = direct(chat, 'workspace_current')['data']['project']
            assert current['id'] == 'engine-demo' and len(current['pins']) == 2
            assert current['snapshots'][0]['id'] == 'baseline' and current['snapshots'][0]['complete']
            assert source.read_text() == original, 'Read-only project tools changed source.'
            baseline = direct(chat, 'workspace_diff', id='baseline')
            assert baseline['data']['unchanged'], baseline
            # Owner-side modification, separate from model/tools and managed rollback.
            changed = original.replace('x * 2', 'x * 3')
            source.write_text(changed)
            (project/'src'/'added.py').write_text('def added(): return 9\n')
            chat.turn('The owner has changed project files outside the managed kernel. Compare the saved '
                      'baseline with actual current source using workspace_diff. Read the changed engine file '
                      'and rebuild pinned context. Identify the exact implementation/contract disagreement, '
                      'changed pin, and added file from receipts. Do not overwrite the baseline or alter files.')
            delta = direct(chat, 'workspace_diff', id='baseline')['data']
            assert delta['comparison_complete'] and not delta['unchanged']
            assert [f['path'] for f in delta['changes']['changed']] == ['src/engine.py']
            assert [f['path'] for f in delta['changes']['added']] == ['src/added.py']
            context = direct(chat, 'workspace_context', query='Engine')['data']
            engine = next(f for f in context['files'] if f['path'] == 'src/engine.py')
            assert engine['changed_since_pin'] and engine['sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
            assert 'return x * 3' in engine['content']
            assert source.read_text() == changed
            required = {'lfe_workspace_open', 'lfe_workspace_tree', 'lfe_workspace_grep',
                        'lfe_workspace_symbols', 'lfe_workspace_read_lines', 'lfe_workspace_pin',
                        'lfe_workspace_snapshot', 'lfe_workspace_context', 'lfe_workspace_diff'}
            assert required <= set(chat.called), required-set(chat.called)
            assert all(r['result']['status'] == 'ok' for r in chat.receipts), chat.receipts
            revision = bridge.revision
            bridge.close()
            bridge = Bridge(store)
            recovered = Chat.__new__(Chat)
            recovered.bridge, recovered.tools = bridge, TOOLS
            p = direct(recovered, 'workspace_current')['data']['project']
            assert p['id'] == current['id'] and p['pins'] == current['pins'] and p['snapshots'] == current['snapshots']
            assert not direct(recovered, 'workspace_diff', id='baseline')['data']['unchanged']
            assert bridge.revision == revision
            jobs = bridge.request('execute', source='(length (jiti_processes:all))')
            assert jobs['value'] == '0'
            report.update(status='passed', revision=revision, delta=delta, evidence_bundle=context,
                          no_source_execution=True, recovered_project_and_pins=True, no_job_replay=True)
        except Exception as error:
            report.update(status='failed', error_type=type(error).__name__)
            raise
        finally:
            if bridge:
                bridge.close()
            if chat:
                report.update(requests=chat.request_count, called_tools=chat.called, usage=chat.usage,
                              receipts=chat.receipts)
            report['finished_at'] = time.time()
            (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
            print(json.dumps({k: report.get(k) for k in ('status', 'model', 'requests', 'revision', 'recovered_project_and_pins')}), flush=True)


if __name__ == '__main__':
    main()
