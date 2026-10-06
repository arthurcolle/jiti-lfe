#!/usr/bin/env python3
"""Explicit bounded real chat, native plans, receipt verification and recovery."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from lfe_repl import Bridge, Chat, FrontendError
from lfe_native_plans import result_check


class Output:
    def __init__(self):
        self.events = []

    def text(self, value):
        self.events.append({'message': value})
        print(value, flush=True)

    def result(self, value, **kwargs):
        self.events.append({'result': value})
        print(json.dumps({k: value[k] for k in ('status', 'revision', 'plan_version', 'ready', 'reason')
                          if k in value}), flush=True)


class BoundedChat(Chat):
    def _response(self):
        if self.request_count >= 20:
            raise FrontendError('Live test reached its declared 20-request ceiling.')
        print(f'Model request {self.request_count + 1}/20', flush=True)
        return super()._response()

    def _tool(self, call):
        self.called_tools.append(call['name'])
        return super()._tool(call)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--model')
    args = parser.parse_args()
    output = args.output or Path(tempfile.mkdtemp(prefix='jiti-native-plans-live-'))
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    store = output / 'store'
    if (store / 'CURRENT').exists():
        parser.error('Use a fresh output: this test never replays a previous workflow.')
    plan = 'verified-pipeline'
    sales = "(timer:sleep 25000) (lists:sum (lists:map (lambda (r) (* (element 1 r) (element 2 r))) '(#(2 15) #(1 40) #(3 10))))"
    invalid = "(timer:sleep 25000) (length (lists:filter (lambda (n) (< n 0)) '(1 2 -3 4 -5)))"
    join = (f"(let ((nodes (map-get (jiti_plan:inspect #B(\"{plan}\")) 'nodes))) "
            "(if (andalso (=:= (map-get (map-get (map-get nodes #B(\"sales\")) 'job) 'result) #B(\"#(ok 100)\")) "
            "(=:= (map-get (map-get (map-get nodes #B(\"invalid\")) 'job) 'result) #B(\"#(ok 2)\"))) "
            "(tuple 'validated 100 2) (error 'upstream_receipts_failed)))")
    contract = [{'id': 'sales', 'source': sales, 'check': result_check(plan, 'sales', '100'), 'dependencies': []},
                {'id': 'invalid', 'source': invalid, 'check': result_check(plan, 'invalid', '2'), 'dependencies': []},
                {'id': 'join', 'source': join, 'check': result_check(plan, 'join', '#(validated 100 2)'),
                 'dependencies': ['sales', 'invalid']}]
    prompt = (f'Build and complete a durable plan named {plan} using the native plan tools. '
              'Here is the exact owner acceptance contract: ' + json.dumps(contract) +
              ' Preserve these source expressions, checks and dependencies exactly. Create task nodes under no parent '
              '(parent=""), each with timeout_ms=60000 and priority=0. Start the two independent jobs before '
              'reconciling or verifying either; they should overlap. Reconcile existing receipts, verify each '
              'stored check, then launch and verify join. Use current returned versions. Never replace checks '
              'with trivial predicates, never redefine kernel helpers, and never start any other jobs. '
              'A running receipt is not completion. Wait with plan_wait (wait_ms=30000); never use timer:sleep '
              'inside an owner evaluation to wait. Use plan tools for all planning actions. Report actual results.')
    sink = Output()
    report = {'status': 'started', 'started_at': time.time(), 'request_ceiling': 20,
              'max_simultaneous_local_jobs': 2, 'contract': contract}
    bridge, chat = None, None
    try:
        bridge = Bridge(store)
        chat = BoundedChat(bridge, sink, model=args.model, tool_limit=18, timeout=60)
        chat.called_tools = []
        report['model'] = chat.model
        chat.turn(prompt)
        final = bridge.request('plan_status', id=plan)
        assert final['status'] == 'ok' and len(final['nodes']) == 3, final
        assert all(n['status'] == 'done' for n in final['nodes']), final
        by_id = {n['id']: n for n in final['nodes']}
        for name, result in [('sales', '#(ok 100)'), ('invalid', '#(ok 2)'), ('join', '#(ok #(validated 100 2))')]:
            assert by_id[name]['result'] == result, by_id[name]
        overlap = min(by_id[n]['finished_at'] for n in ('sales', 'invalid')) - max(
            by_id[n]['started_at'] for n in ('sales', 'invalid'))
        assert overlap > 0, 'The independent workers did not actually overlap.'
        assert by_id['join']['started_at'] >= max(by_id[n]['finished_at'] for n in ('sales', 'invalid'))
        no_extra_jobs = bridge.request('execute', source='(=:= (length (jiti_processes:all)) 3)')
        assert no_extra_jobs['value'] == 'true', no_extra_jobs
        source_check = f"(map-get (jiti_plan:inspect #B(\"{plan}\")) 'nodes)"
        clauses = []
        for task in contract:
            node = f"(map-get {source_check} #B(\"{task['id']}\"))"
            # Quote with numeric binaries exactly as the native adapter does.
            from lfe_plan_tools import binary
            clauses.extend([f"(=:= (map-get {node} 'check) {binary(task['check'])})",
                            f"(=:= (map-get (map-get {node} 'spec) 'source) {binary(task['source'])})"])
        accepted_contract = bridge.request('execute', source='(andalso ' + ' '.join(clauses) + ')')
        assert accepted_contract['value'] == 'true', accepted_contract
        assert 'lfe_plan_create' in chat.called_tools and 'lfe_plan_verify' in chat.called_tools
        report.update(status='completed', final=final, actual_worker_overlap_ms=overlap,
                      exact_owner_contract_preserved=accepted_contract, no_extra_jobs=no_extra_jobs)
        bridge.close()
        bridge = Bridge(store)
        recovered = bridge.request('plan_status', id=plan)
        assert all(n['status'] == 'done' for n in recovered['nodes'])
        no_replay = bridge.request('execute', source='(=:= (jiti_processes:all) ())')
        assert no_replay['value'] == 'true', no_replay
        report.update(recovery=recovered, no_replayed_jobs=no_replay)
    except (AssertionError, FrontendError, OSError) as error:
        report.update(status='failed', error_type=type(error).__name__)
        raise
    finally:
        if bridge is not None:
            bridge.close()
        if chat is not None:
            report.update(model_requests=chat.request_count, usage=chat.usage, called_tools=chat.called_tools)
        report.update(finished_at=time.time(), events=sink.events, monetary_charges='unknown')
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(str(output / 'report.json'), flush=True)


if __name__ == '__main__':
    main()
