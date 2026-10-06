#!/usr/bin/env python3
"""Offline chat-count-limit regression tests; no credentials, HTTP or BEAM."""
import contextlib
import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import lfe_repl as m

class Output:
    def text(self, value): pass
    def result(self, value, op=None, compact=False): pass

def chat(limit, batches):
    c = m.Chat.__new__(m.Chat)
    c.bridge = SimpleNamespace(broken=False)
    c.output = Output()
    c.tool_limit = limit
    c.items = []
    c.executed = []
    replies = iter(batches)
    c._response = lambda: next(replies)
    def tool(call):
        c.executed.append(call['call_id'])
        return {'status': 'ok'}
    c._tool = tool
    return c

def call(n):
    return {'type': 'function_call', 'call_id': str(n), 'name': 'lfe_status', 'arguments': '{}'}

class ToolLimits(unittest.TestCase):
    def test_unlimited_crosses_old_limit(self):
        c = chat(0, [[call(n)] for n in range(40)] + [[]])
        c.turn('continue')
        self.assertEqual(c.executed, [str(n) for n in range(40)])

    def test_finite_limit_does_not_execute_rejected_calls(self):
        c = chat(3, [[call(n)] for n in range(5)])
        with self.assertRaises(m.FrontendError): c.turn('continue')
        self.assertEqual(c.executed, ['0', '1', '2'])
        receipts = [x for x in c.items if x.get('type') == 'function_call_output']
        self.assertEqual(len(receipts), 4)
        self.assertIn('rejected', receipts[-1]['output'])

    def test_parser_default_and_unlimited(self):
        self.assertEqual(m.parser().parse_args([]).tool_limit, 0)
        self.assertEqual(m.parser().parse_args(['--tool-limit', '0']).tool_limit, 0)
        self.assertEqual(m.parser().parse_args(['--tool-limit', '200']).tool_limit, 200)

    def test_negative_cli_limit_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit): m.parser().parse_args(['--tool-limit', '-1'])

    def test_session_change_and_invalid_input(self):
        s = m.Session(SimpleNamespace(broken=False), Output(), SimpleNamespace(mode='lfe', tool_limit=12))
        s.chat = SimpleNamespace(tool_limit=12)
        self.assertTrue(s.run('/tool-limit 0'))
        self.assertEqual(s.options.tool_limit, 0)
        self.assertEqual(s.chat.tool_limit, 0)
        self.assertTrue(s.run('/tool-limit'))
        with self.assertRaises(m.FrontendError): s.run('/tool-limit -1')
        self.assertEqual(s.options.tool_limit, 0)
        self.assertTrue(s.run('/tool-limit 25'))
        self.assertEqual(s.chat.tool_limit, 25)

    def test_keyboard_interrupt_still_propagates(self):
        c = chat(0, [])
        def interrupted(): raise KeyboardInterrupt
        c._response = interrupted
        with self.assertRaises(KeyboardInterrupt): c.turn('continue')
        self.assertEqual(c.executed, [])

if __name__ == '__main__': unittest.main()
