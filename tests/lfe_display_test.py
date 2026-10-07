#!/usr/bin/env python3
"""Frontend-only tests: no bridge, provider, or active store required."""
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
from types import SimpleNamespace
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from lfe_repl import Bridge, Chat, Output, Session, chat_receipt, parser, display_preview, terminal_text

class DisplayTests(unittest.TestCase):
    def result(self, **extra):
        return dict(status='ok', revision=6, goal=False, state='#M(secret-state 1)', value='', reason='', **extra)
    def capture(self, output, result, **kwargs):
        stream = io.StringIO()
        with redirect_stdout(stream):
            output.result(result, **kwargs)
        return stream.getvalue()
    def test_compact_does_not_mutate(self):
        result = self.result(content='line' + chr(10) + 'x' * 5000, workspace_path='source.py')
        before = copy.deepcopy(result)
        output = Output()
        text = self.capture(output, result, op='lfe_workspace_read', compact=True)
        self.assertNotIn('secret-state', text)
        self.assertIn('workspace_read | ok | rev 6', text)
        self.assertIn('/details', text)
        self.assertEqual(result, before)
        self.assertIs(output.last_result, result)
    def test_json_unchanged(self):
        result = self.result()
        self.assertEqual(json.loads(self.capture(Output(True), result, compact=True)), result)
    def test_full_result(self):
        self.assertIn('secret-state', self.capture(Output(), self.result(), compact=False))
    def test_default_does_not_dump_state(self):
        text = self.capture(Output(), self.result())
        self.assertNotIn('secret-state', text)
        self.assertNotIn('goal=false', text)
    def test_pause_visible(self):
        result = self.result(token=31)
        result.update(status='paused', reason='reader_failed')
        text = self.capture(Output(), result, compact=True)
        for expected in ('paused', 'token=31', 'reader_failed', '/repair', '/abort'):
            self.assertIn(expected, text)
    def test_details_is_local(self):
        class NoRequests:
            def request(self, *args, **kwargs):
                raise AssertionError('Details must not execute a kernel operation')
        output = Output()
        output.last_result = self.result()
        session = Session(NoRequests(), output, SimpleNamespace(mode='chat'))
        stream = io.StringIO()
        with redirect_stdout(stream):
            self.assertTrue(session.run('/details'))
        self.assertIn('secret-state', stream.getvalue())
    def test_control_escape(self):
        text = terminal_text(chr(27) + '[31m' + chr(0x202e))
        self.assertNotIn(chr(27), text)
        self.assertNotIn(chr(0x202e), text)
    def test_term_types_not_guessed(self):
        for term in ('#B(0 255 106)', '#B(106 105 ...)', '(65 66 67)', '#B(106 105 116 105)'):
            self.assertEqual(display_preview(term), term)
    def test_bounded_preview(self):
        self.assertIn('/details', display_preview(('line' + chr(10)) * 100))
        self.assertEqual(display_preview('small'), 'small')
    def test_context_tool_keeps_last_kernel_receipt(self):
        output = Output()
        receipt = self.result()
        output.last_result = receipt
        self.capture(output, {'bytes': 1200, 'kernel_changed': False})
        self.assertIs(output.last_result, receipt)
    def test_chat_activity_keeps_raw_details_without_echoing_values(self):
        output = Output()
        receipt = self.result(data={'value_display': '#M(status blocked)'})
        stream = io.StringIO()
        with redirect_stdout(stream):
            output.tool_result(receipt, op='lfe_state_get')
        self.assertEqual(stream.getvalue(), 'state_get | ok | rev 6\n')
        self.assertIs(output.last_result, receipt)

class DeveloperWorkflow(unittest.TestCase):
    def test_native_pretty_view_marks_elided_binary_and_preserves_types(self):
        with tempfile.TemporaryDirectory(prefix='jiti-native-view-') as store:
            bridge = Bridge(store)
            try:
                for source, shortened in [('(lists:duplicate 60 65)', False),
                                          ('(list_to_binary (lists:duplicate 60 65))', False),
                                          ('(list_to_binary (lists:duplicate 60 0))', True),
                                          ("(map 'payload (list_to_binary (lists:duplicate 60 0)))", True),
                                          ('(cons 1 2)', True)]:
                    result = bridge.request('execute', source=source)
                    self.assertEqual(result['status'], 'ok')
                    self.assertEqual(result['display_truncated'], shortened, result)
                self.assertEqual(bridge.revision, 0)
            finally:
                bridge.close()

    def test_actual_launcher_pause_repair_and_exit(self):
        with tempfile.TemporaryDirectory(prefix='jiti-cli-workflow-') as store:
            command = [sys.executable, '-B', str(Path(__file__).resolve().parents[1] / 'scripts/repl.py'),
                       '--store', store, '--plain']
            process = subprocess.run(command, input='(missing 4)\n/status\n/repair (defun missing (x) (+ x 1))\n/retry\n/exit\n',
                                     text=True, capture_output=True, timeout=20)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn('paused', process.stdout)
            self.assertIn('/repair', process.stdout)
            self.assertIn('value: 5', process.stdout)
            self.assertIn('Session closed at revision 1', process.stdout)
            self.assertNotIn('state: #M', process.stdout)
            self.assertLess(len(process.stdout), 1500)

    def test_real_inspection_and_exit_without_state_flood(self):
        with tempfile.TemporaryDirectory(prefix='jiti-display-') as store:
            bridge = Bridge(store)
            try:
                bridge.request('execute', source='(state-put \'large (lists:duplicate 100000 120))')
                source = '(state-put \'diagnosis (map \'status \'blocked \'conditions (map \'y (map \'status \'unknown \'expected \'true)) \'unresolved \'(y)))'
                result = bridge.request('execute', source=source)
                self.assertIn('unknown', result['value_display'])
                before = bridge.revision
                output = Output()
                session = Session(bridge, output, parser().parse_args([]))
                stream = io.StringIO()
                with redirect_stdout(stream):
                    for command in ('/status', '/state', '/state diagnosis', '/state absent', '/functions', '/jobs', '/notes', '/help'):
                        self.assertTrue(session.run(command))
                text = stream.getvalue()
                self.assertLess(len(text), 3000)
                self.assertIn('diagnosis (atom)', text)
                self.assertIn('unresolved (y)', text)
                self.assertIn('Key not found', text)
                self.assertIn('/help all', text)
                self.assertNotIn('state: #M', text)
                self.assertEqual(bridge.revision, before)
                with redirect_stdout(io.StringIO()):
                    self.assertFalse(session.run('/exit'))
            finally:
                bridge.close()
            recovered = Bridge(store)
            try:
                self.assertEqual(recovered.revision, before)
                self.assertEqual(recovered.request('execute', source="(map-get (state-get 'diagnosis) 'status)")['value'], 'blocked')
            finally:
                recovered.close()

    def test_chat_growth_and_receipt_fidelity_with_real_bridge(self):
        with tempfile.TemporaryDirectory(prefix='jiti-chat-display-') as store:
            bridge = Bridge(store)
            try:
                bridge.request('execute', source="(state-put 'large (lists:duplicate 100000 120))")
                result = bridge.request('execute', source='(missing 1)')
                projected = chat_receipt(result)
                for key in ('status', 'reason', 'token', 'revision', 'operation_id'):
                    self.assertEqual(projected[key], result[key])
                self.assertNotIn('state', projected)
                bridge.request('abort')
                chat = Chat.__new__(Chat)
                chat.bridge, chat.output = bridge, Output()
                chat.model, chat.instructions, chat.tools = 'offline', 'test', []
                chat.items, chat.tool_limit, chat.max_output_tokens = [], 0, 8192
                # 100 real read-only tool exchanges; provider replies are offline.
                batches = iter([[{'type': 'function_call', 'call_id': str(n), 'name': 'lfe_status', 'arguments': '{}'}]
                                for n in range(100)] + [[]])
                chat._response = lambda: (chat._ensure_context(), next(batches))[1]
                chat._tool = lambda call: bridge.request('status')
                with redirect_stdout(io.StringIO()):
                    chat.turn('Inspect the application without changing it')
                receipts = [json.loads(i['output']) for i in chat.items if i.get('type') == 'function_call_output']
                self.assertEqual(len(receipts), 100)
                self.assertTrue(all('state' not in r and r['revision'] == 1 for r in receipts))
                self.assertLess(chat.context()['bytes'], 100 * 1024)
                self.assertEqual(bridge.revision, 1)
            finally:
                bridge.close()

if __name__ == '__main__':
    unittest.main()
