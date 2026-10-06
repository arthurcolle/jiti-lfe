#!/usr/bin/env python3
"""Explicit bounded live Responses smoke for the added typed tool suite."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from lfe_repl import Bridge, Chat, FrontendError, TOOLS
from lfe_toolkit import TOOLKIT_TOOLS
from lfe_plan_tools import binary


class Output:
    def text(self, value):
        print(value, flush=True)

    def result(self, result, **kwargs):
        print(json.dumps({k: result[k] for k in ('status', 'revision', 'reason') if k in result}), flush=True)


class BoundedChat(Chat):
    def _response(self):
        if self.request_count >= 24:
            raise FrontendError('Live smoke reached its declared 24-request ceiling.')
        print(f'Model request {self.request_count + 1}/24', flush=True)
        return super()._response()

    def _tool(self, call):
        self.calls.append(call['name'])
        return super()._tool(call)


def request(chat, op, **args):
    return Chat._tool(chat, {'name': 'lfe_' + op, 'arguments': json.dumps(args)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model')
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    store = args.output / 'store'
    if (store / 'CURRENT').exists():
        parser.error('Use a fresh output directory; this test never replays a prior workflow.')
    report = dict(status='started', started_at=time.time(), request_ceiling=24,
                  tool_ceiling=22, added_tools=len(TOOLKIT_TOOLS), native_tools=len(TOOLS))
    bridge, chat = None, None
    body = '(lists:sum (lists:map (lambda (r) (* (map-get r #B("qty")) (map-get r #B("price")))) rows))'
    rows = [{'qty': 2, 'price': 15}, {'qty': 1, 'price': 40}, {'qty': 3, 'price': 10}]
    prompt = (
        'Use the new typed tools to complete this exact local smoke task, and report real receipts. '
        'Do not use generic develop/execute/preview, plan tools, or workspace tools. '
        '1. Discover the available function tools with tools_list. '
        '2. Define managed function invoice-total, arguments ["rows"], documentation "Sum qty times price", '
        'body exactly ' + json.dumps(body) + '. '
        '3. Test it with two cases: args_json=' + json.dumps(json.dumps([rows])) +
        ', expected_json="100"; args_json="[[]]", expected_json="0". Both must pass. '
        '4. Call it using the same rows and confirm 100. '
        '5. Put binary managed key last-invoice with value_json="100", and read it back. '
        '6. Start exactly one named job invoice-audit, timeout_ms=2000, '
        'source exactly "(timer:sleep 200) (+ 98 2)". Use job_wait to reconcile its actual result. '
        '7. Save a durable note invoice-result with text exactly "Verified invoice total: 100" '
        'and tags ["invoice", "verified"], then read it. '
        'Use preview=false for required edits and actual current expected_revision. '
        'Do not redefine system helpers or create any other jobs. Use only the added typed tools '
        'and lfe_status if needed. Testing, execution and note storage are separate actions.')
    try:
        bridge = Bridge(store)
        chat = BoundedChat(bridge, Output(), model=args.model, tool_limit=22, timeout=60)
        chat.calls = []
        report['model'], report['advertised_tools'] = chat.model, len(chat.tools)
        chat.turn(prompt)
        test = request(chat, 'function_test', name='invoice-total', cases=[
            {'args_json': json.dumps([rows]), 'expected_json': '100'},
            {'args_json': '[[]]', 'expected_json': '0'}])
        assert test['status'] == 'ok' and test['data']['passed'], test
        state = request(chat, 'state_get', key='last-invoice', key_kind='binary')
        assert json.loads(state['data']['value_json']) == 100, state
        note = request(chat, 'note_get', id='invoice-result')
        assert note['data']['text'] == 'Verified invoice total: 100', note
        job = request(chat, 'job_status', id='invoice-audit')
        assert job['data']['recorded_status'] == 'succeeded' and job['data']['recorded_handle']['result'] == '#(ok 100)', job
        assert request(chat, 'job_list', offset=0)['data']['runtime_job_count'] == 1
        source = request(chat, 'function_source', name='invoice-total', arity=1, offset=0)
        expected = '(defun invoice-total (rows) "Sum qty times price" ' + body + ')'
        same = bridge.request('execute', source='(=:= (lfe_io:read_string (unicode:characters_to_list ' +
                              binary(expected) + ')) (lfe_io:read_string (unicode:characters_to_list ' +
                              binary(source['data']['source']) + ')))')
        assert same['status'] == 'ok' and same['value'] == 'true', same
        required = {'lfe_tools_list', 'lfe_function_define', 'lfe_function_test', 'lfe_function_call',
                    'lfe_state_put', 'lfe_state_get', 'lfe_job_start', 'lfe_job_wait', 'lfe_note_put', 'lfe_note_get'}
        assert required <= set(chat.calls), required - set(chat.calls)
        assert set(chat.calls) <= {'lfe_' + op for op in TOOLKIT_TOOLS} | {'lfe_status'}, chat.calls
        revision = bridge.revision
        bridge.close()
        bridge = Bridge(store)
        recovered = Chat.__new__(Chat)
        recovered.bridge, recovered.tools = bridge, TOOLS
        assert request(recovered, 'note_get', id='invoice-result')['data']['text'] == note['data']['text']
        assert json.loads(request(recovered, 'state_get', key='last-invoice', key_kind='binary')['data']['value_json']) == 100
        after = request(recovered, 'job_status', id='invoice-audit')['data']
        assert after['recorded_status'] == 'succeeded' and after['observed_status'] == 'unknown'
        assert request(recovered, 'job_list', offset=0)['data']['runtime_job_count'] == 0
        assert bridge.revision == revision
        report.update(status='passed', revision=revision, recovered_without_replay=True,
                      exact_source_verified=True, result=100, note=note['data'], job=job['data'])
    except Exception as error:
        report.update(status='failed', error_type=type(error).__name__)
        raise
    finally:
        if chat:
            report.update(requests=chat.request_count, called_tools=chat.calls, usage=chat.usage)
        report['finished_at'] = time.time()
        if bridge:
            bridge.close()
        (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({k: report.get(k) for k in ('status', 'model', 'requests', 'result', 'recovered_without_replay')}), flush=True)


if __name__ == '__main__':
    main()
