#!/usr/bin/env python3
"""Actual source inspection, managed workspace lifecycle and recovery tests."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from lfe_repl import Bridge, Chat, FrontendError, Output, Session, TOOLS
from lfe_toolkit import WORKSPACE_TOOLS

SEEN = set()


def chat(bridge):
    c = Chat.__new__(Chat)
    c.bridge, c.tools = bridge, TOOLS
    return c


def tool(c, op, **args):
    SEEN.add(op)
    return c._tool({'name': 'lfe_' + op, 'arguments': json.dumps(args)})


def edit(c, op, **args):
    args.setdefault('expected_revision', c.bridge.revision)
    args.setdefault('preview', False)
    return tool(c, op, **args)


def ok(result):
    assert result['status'] == 'ok', result
    return result['data']


def reject(result, reason):
    assert result['status'] == 'rejected' and result['reason'] == reason and 'token' not in result, result


def open_project(c, directory, id='demo', **args):
    return edit(c, 'workspace_open', id=id, root='jiti/'+directory.relative_to(ROOT).as_posix(),
                title='Fixture project', description='Contracts and source evidence', **args)


def fixtures(directory):
    (directory/'src').mkdir()
    (directory/'docs').mkdir()
    (directory/'node_modules').mkdir()
    (directory/'README.md').write_text('# Project fixture\nEngine acceptance: DOUBLE\n')
    (directory/'docs'/'contract.md').write_text('# Contract\nEngine.run returns x * 2.\n')
    (directory/'src'/'engine.py').write_text(
        'class Engine:\n    def run(self, x):\n        return x * 2\n\n'
        'def call_engine(x):\n    return Engine().run(x)\n')
    (directory/'src'/'never_import.py').write_text('raise RuntimeError("source must never execute")\ndef observed_only():\n    return 7\n')
    (directory/'src'/'types.lfe').write_text('(defmodule engine (export (double 1)))\n(defun double (x) (* x 2))\n')
    (directory/'node_modules'/'ignored.py').write_text('def forbidden_vendor_hit(): pass\n')
    (directory/'.hidden.py').write_text('def hidden_hit(): pass\n')
    (directory/'secret.txt').write_text('not an allowed source type\n')
    (directory/'link.py').symlink_to(directory/'src'/'engine.py')


def lifecycle(directory, stores):
    store = stores/'lifecycle'
    with contextlib.closing(Bridge(store)) as b:
        c = chat(b)
        assert not ok(tool(c, 'workspace_current'))['selected']
        reject(tool(c, 'workspace_grep', path='', query='Engine', case_sensitive=True), 'workspace_no_project')
        ok(open_project(c, directory, preview=True))
        assert b.revision == 0 and not ok(tool(c, 'workspace_current'))['selected']
        p = ok(open_project(c, directory))
        assert p['id'] == 'demo' and b.revision == 1
        assert ok(tool(c, 'workspace_projects', offset=0))['count'] == 1
        file = directory/'src'/'engine.py'
        metadata = ok(tool(c, 'workspace_stat', path='src/engine.py'))
        assert metadata['file_bytes'] == file.stat().st_size and metadata['kind'] == 'regular'
        rev = b.revision
        with patch.object(b, 'request', wraps=b.request) as calls:
            reject(edit(c, 'workspace_pin', path='src/engine.py', label='Entry point', action='add',
                        expected_revision=rev-1), 'stale_revision')
            assert all(call.args[0] == 'status' for call in calls.call_args_list)
        assert b.revision == rev
        ok(edit(c, 'workspace_pin', path='src/engine.py', label='Entry point', action='add', preview=True))
        assert not ok(tool(c, 'workspace_current'))['project']['pins']
        pin = ok(edit(c, 'workspace_pin', path='src/engine.py', label='Entry point', action='add'))['pins'][0]
        assert pin['sha256'] == hashlib.sha256(file.read_bytes()).hexdigest()
        ok(edit(c, 'workspace_pin', path='docs/contract.md', label='Acceptance', action='add'))
        context = ok(tool(c, 'workspace_context', query='Engine.run'))
        assert context['evidence_only'] and context['files'] and not context['files'][0]['changed_since_pin']
        read = ok(tool(c, 'workspace_read_lines', path='src/engine.py', start_line=2, line_count=2))
        assert read['start_line'] == 2 and read['end_line'] == 3 and 'return x * 2' in read['content']
        assert read['sha256'] == pin['sha256'] and read['next_line'] == 4
        tree = ok(tool(c, 'workspace_tree', path='', offset=0))
        assert tree['complete'] and tree['next_offset'] is None
        paths = [e['path'] for e in tree['entries']]
        assert 'src/engine.py' in paths and 'link.py' not in paths and '.hidden.py' not in paths
        assert 'node_modules/ignored.py' not in paths and 'secret.txt' not in paths
        assert any(e['reason'] == 'symlink' for e in tree['excluded'])
        grep = ok(tool(c, 'workspace_grep', path='', query='engine', case_sensitive=False))
        assert grep['coverage']['complete'] and any(h['path'] == 'docs/contract.md' for h in grep['hits'])
        mapped = ok(tool(c, 'workspace_symbols', path='src', query='run', offset=0))
        assert any(s['name'] == 'run' and s['line'] == 2 and s['parser'] == 'lexical' for s in mapped['symbols'])
        observed = ok(tool(c, 'workspace_symbols', path='src/never_import.py', query='observed_only', offset=0))
        assert observed['symbols'][0]['name'] == 'observed_only'
        lfe = ok(tool(c, 'workspace_symbols', path='src/types.lfe', query='double', offset=0))
        assert lfe['symbols'][0]['parser'] == 'lexical'
        refs = ok(tool(c, 'workspace_references', path='', symbol='Engine'))
        assert refs['match_kind'] == 'lexical_identifier' and len(refs['hits']) >= 3
        rev = b.revision
        preview = ok(edit(c, 'workspace_snapshot', id='preview', preview=True))
        assert preview['manifest']['complete'] and b.revision == rev
        reject(tool(c, 'workspace_diff', id='preview'), 'workspace_snapshot_not_found')
        snapshot = ok(edit(c, 'workspace_snapshot', id='baseline'))
        assert snapshot['manifest']['complete'] and len(snapshot['manifest']['files']) == 5
        rev = b.revision
        repeated = ok(edit(c, 'workspace_snapshot', id='baseline'))
        assert repeated['reused'] and b.revision == rev
        unchanged = ok(tool(c, 'workspace_diff', id='baseline'))
        assert unchanged['unchanged'] and unchanged['comparison_complete']
        # Only inspect fixture files; workspace actions never write project source.
        file.write_text(file.read_text().replace('x * 2', 'x * 3'))
        (directory/'README.md').unlink()
        (directory/'src'/'new.py').write_text('def new_feature(): return 42\n')
        delta = ok(tool(c, 'workspace_diff', id='baseline'))
        assert [e['path'] for e in delta['changes']['changed']] == ['src/engine.py']
        assert [e['path'] for e in delta['changes']['removed']] == ['README.md']
        assert [e['path'] for e in delta['changes']['added']] == ['src/new.py']
        assert delta['comparison_complete'] and not delta['unchanged']
        assert any(f['changed_since_pin'] for f in ok(tool(c, 'workspace_context', query='Engine'))['files'])
        reject(edit(c, 'workspace_snapshot', id='baseline'), 'workspace_snapshot_exists')
        # Switching scopes retains each project's pins and snapshots.
        ok(open_project(c, directory/'src', id='source-only'))
        assert ok(tool(c, 'workspace_current'))['project']['root'].endswith('/src')
        ok(edit(c, 'workspace_use', id='demo'))
        reject(open_project(c, directory/'src', id='demo'), 'workspace_project_root_conflict')
        assert len(ok(tool(c, 'workspace_current'))['project']['pins']) == 2
        rev = b.revision
        ok(edit(c, 'workspace_pin', path='docs/contract.md', label='', action='remove'))
        assert len(ok(tool(c, 'workspace_current'))['project']['pins']) == 1
        assert b.request('rollback', revision=rev)['status'] == 'ok'
        assert len(ok(tool(c, 'workspace_current'))['project']['pins']) == 2
        accepted = b.revision
    with contextlib.closing(Bridge(store)) as b:
        c = chat(b)
        current = ok(tool(c, 'workspace_current'))
        assert current['project']['id'] == 'demo' and len(current['project']['pins']) == 2
        assert current['project']['snapshots'][0]['id'] == 'baseline'
        assert not ok(tool(c, 'workspace_diff', id='baseline'))['unchanged']
        assert b.revision == accepted
        assert b.request('execute', source='(length (jiti_processes:all))')['value'] == '0'


def limits(directory, stores):
    directory.mkdir()
    for n in range(132):
        (directory/f'f{n:03d}.py').write_text(f'def fn{n}(): return {n}\n')
    with contextlib.closing(Bridge(stores/'limits')) as b:
        c = chat(b)
        ok(open_project(c, directory))
        tree = ok(tool(c, 'workspace_tree', path='', offset=0))
        assert not tree['complete'] and len(tree['entries']) == 100 and tree['next_offset'] == 100
        page = ok(tool(c, 'workspace_tree', path='', offset=100))
        assert len(page['entries']) == 28 and page['next_offset'] is None
        saved = ok(edit(c, 'workspace_snapshot', id='bounded'))
        assert len(saved['manifest']['files']) == 128 and not saved['manifest']['complete']
        compared = ok(tool(c, 'workspace_diff', id='bounded'))
        assert not compared['comparison_complete'] and not compared['unchanged']
        hits = ok(tool(c, 'workspace_grep', path='', query='def', case_sensitive=True))
        assert len(hits['hits']) == 50 and hits['matches_truncated']
        # Every valid pin remains independently bounded by its source-byte cap.
        (directory/'huge.py').write_bytes(b'#'+b'x'*262144)
        reject(edit(c, 'workspace_pin', path='huge.py', label='', action='add'), 'workspace_file_byte_limit')
        (directory/'long.py').write_text('#'+'x'*13000+'\ndef tail(): return 7\n')
        view = ok(tool(c, 'workspace_read_lines', path='long.py', start_line=1, line_count=2))
        assert view['content_truncated'] and len(view['content']) == 12000
        # UTF-8 is reconstructed across native 12000-byte chunks.
        (directory/'unicode.md').write_text('a'*11999+'é evidence\n', encoding='utf-8')
        utf8 = ok(tool(c, 'workspace_read_lines', path='unicode.md', start_line=1, line_count=1))
        assert utf8['encoding'] == 'utf-8'
        (directory/'folded.md').write_text('Straße Engine\n', encoding='utf-8')
        folded = ok(tool(c, 'workspace_grep', path='folded.md', query='engine', case_sensitive=False))
        assert folded['hits'][0]['column'] == 8 and 'Engine' in folded['hits'][0]['excerpt']
        (directory/'long-match.md').write_text('x'*1500+' Engine\n')
        long_hit = ok(tool(c, 'workspace_grep', path='long-match.md', query='Engine', case_sensitive=True))
        assert long_hit['hits'][0]['column'] == 1502 and 'Engine' in long_hit['hits'][0]['excerpt']


def byte_budget(directory, stores):
    directory.mkdir()
    for i in range(10):
        (directory/f'large{i}.py').write_bytes(b'#'+b'x'*259999)
    with contextlib.closing(Bridge(stores/'bytes')) as b:
        c = chat(b)
        ok(open_project(c, directory))
        snapshot = ok(edit(c, 'workspace_snapshot', id='partial'))
        manifest = snapshot['manifest']
        assert manifest['bytes_read'] <= 2*1024*1024 and not manifest['complete']
        assert manifest['skipped'] and len(manifest['files']) == 8
        compared = ok(tool(c, 'workspace_diff', id='partial'))
        assert not compared['comparison_complete'] and compared['coverage']['bytes_read'] <= 2*1024*1024
        # The native reader rejects oversize reads before consuming bytes.
        root = 'jiti/'+directory.relative_to(ROOT).as_posix()+'/large0.py'
        bounded = b.request('execute', source=f'(jiti_workspace:source #B("{root}") 100)')
        assert bounded['status'] == 'ok' and bounded['value'] == '#(error workspace_file_byte_limit 0)'



def rejections(directory, stores):
    with contextlib.closing(Bridge(stores/'reject')) as b:
        c = chat(b)
        ok(open_project(c, directory))
        revision = b.revision
        for path in ('../README.md', '/etc/passwd', '.hidden.py', 'src/../../src/kernel.lisp', 'src\\engine.py'):
            reject(tool(c, 'workspace_stat', path=path), 'workspace_invalid_relative_path')
        reject(tool(c, 'workspace_read_lines', path='link.py', start_line=1, line_count=1), 'workspace_symlink')
        reject(tool(c, 'workspace_stat', path='secret.txt'), 'workspace_source_type_required')
        reject(edit(c, 'workspace_use', id='missing'), 'workspace_project_not_found')
        malformed = [dict(path='', query='x', case_sensitive=1),
                     dict(path='', query='', case_sensitive=True),
                     dict(path='', query='x', case_sensitive=True, extra='x'),
                     dict(path='', query='x')]
        for args in malformed:
            try:
                tool(c, 'workspace_grep', **args)
            except FrontendError:
                pass
            else:
                raise AssertionError('Malformed workspace schema accepted.')
        assert b.revision == revision
        # Literal project metadata never enters generated source unescaped.
        injected = 'p") (state-put \'injected 1) #B("'
        ok(open_project(c, directory, id=injected))
        assert b.request('execute', source="(state-get 'injected)")['value'] == 'undefined'
        assert ok(tool(c, 'workspace_current'))['project']['id'] == injected


def terminal(directory, stores):
    with contextlib.closing(Bridge(stores/'terminal')) as b:
        output = Output(True)
        session = Session(b, output, SimpleNamespace(mode='lfe'))
        relative_root = 'jiti/'+directory.relative_to(ROOT).as_posix()
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            for command in (f'/workspace open demo {relative_root}', '/workspace', '/workspace projects',
                            '/workspace pin src/engine.py "Entry point"', '/workspace tree src',
                            '/workspace symbols Engine', '/workspace grep Engine', '/workspace context Engine',
                            '/workspace snapshot terminal', '/workspace diff terminal'):
                assert session.run(command)
        receipts = [json.loads(line) for line in captured.getvalue().splitlines()]
        assert len(receipts) == 10 and all(r['status'] == 'ok' for r in receipts), receipts
        assert receipts[-1]['data']['unchanged']


def main():
    with tempfile.TemporaryDirectory(prefix='workspace-fixture-', dir=ROOT/'tests') as fixture, \
         tempfile.TemporaryDirectory(prefix='jiti-workspace-stores-') as temporary:
        base, stores = Path(fixture), Path(temporary)
        project = base/'project'
        project.mkdir()
        fixtures(project)
        for scenario, target in ((lifecycle, project), (limits, base/'limits'), (byte_budget, base/'byte-budget'),
                                 (rejections, project), (terminal, project)):
            scenario(target, stores)
            print(scenario.__name__+': passed', flush=True)
    assert set(WORKSPACE_TOOLS) <= SEEN, set(WORKSPACE_TOOLS)-SEEN
    print(f'All {len(WORKSPACE_TOOLS)} project workspace tools exercised against actual BEAM/file observations.')


if __name__ == '__main__':
    main()
