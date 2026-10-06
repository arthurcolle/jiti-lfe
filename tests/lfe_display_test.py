#!/usr/bin/env python3
"""Frontend-only tests: no bridge, provider, or active store required."""
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from lfe_repl import Output, Session, display_preview, terminal_text

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
        self.assertIn('secret-state', self.capture(Output(), self.result()))
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

if __name__ == '__main__':
    unittest.main()
