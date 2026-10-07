"""Exercise the real terminal through a PTY, plus bridge and rendering boundaries."""
import asyncio
import io
import json
import os
from pathlib import Path
import pty
import random
import re
import select
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import fcntl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from terminal_ui import Renderer, WorkspaceHistory, safe_text
from rich.console import Console

ANSI = re.compile(rb'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))')


class Terminal:
    def __init__(self, store, home, extra=(), width=100, environment=None):
        self.trace = []
        self.output = bytearray()
        self.status = None
        env = os.environ.copy()
        env.update(HOME=str(home), TERM='xterm-256color', PROMPT_TOOLKIT_NO_CPR='1')
        for key in ('OPENAI_API_KEY', 'OPENAI_API_KEY_FILE', 'OPENAI_BASE_URL', 'OPENAI_MODEL'):
            env.pop(key, None)
        if environment:
            env.update(environment)
        self.pid, self.fd = pty.fork()
        if not self.pid:
            os.chdir(ROOT)
            os.execve(sys.executable, [sys.executable, str(ROOT / 'scripts/repl.py'), '--legacy', '--store', str(store), *extra], env)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack('HHHH', 30, width, 0, 0))
        self.expect('chat')

    def pump(self, duration=.08):
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            if select.select([self.fd], [], [], max(0, deadline - time.monotonic()))[0]:
                try:
                    chunk = os.read(self.fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                self.output.extend(chunk)
                if b'\x1b[6n' in chunk:
                    os.write(self.fd, b'\x1b[1;1R')

    def text(self):
        return ANSI.sub(b'', bytes(self.output)).decode('utf-8', errors='replace')

    def expect(self, text, timeout=20, start=0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if text in ANSI.sub(b'', bytes(self.output[start:])).decode('utf-8', errors='replace'):
                return
            self.pump(.1)
        raise AssertionError(f'Missing {text!r}:\n{self.text()[-10000:]}')

    def send(self, text):
        self.trace.append(text)
        os.write(self.fd, text.encode('utf-8'))
        self.pump()

    def command(self, text, expected):
        start = len(self.output)
        self.send(text + '\r')
        self.expect(expected, start=start)
        self.pump(.2)

    def close(self, eof=True, expected=0):
        if self.status is not None:
            return
        if eof:
            self.send('\x04')
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            self.pump(.1)
            child, status = os.waitpid(self.pid, os.WNOHANG)
            if child:
                self.status = os.waitstatus_to_exitcode(status)
                os.close(self.fd)
                assert self.status == expected, self.text()
                return
        os.kill(self.pid, signal.SIGTERM)
        os.waitpid(self.pid, 0)
        os.close(self.fd)
        self.status = -1
        raise AssertionError('Terminal did not shut down')


def bridge_checks(directory):
    store = directory / 'bridge'
    child = subprocess.Popen(['sbcl', '--noinform', '--script', 'scripts/terminal.lisp', '--store', str(store)],
                             cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    def until(kind):
        while True:
            line = child.stdout.readline()
            assert line, child.stderr.read()
            event = json.loads(line)
            if event['type'] == kind:
                return event['data']
    def send(message):
        child.stdin.write(json.dumps(message, ensure_ascii=False) + '\n')
        child.stdin.flush()
    try:
        startup = until('startup')
        initial = until('view')['view']
        until('input')
        # Probes classify via the actual Lisp reader without evaluating read-time code.
        cases = [('/execute (list', 'incomplete'), ('/execute (list "(")', 'complete'),
                 ('/execute (list #\\))', 'complete'), ('/execute #.(error "must not run")', 'invalid'),
                 ('Chat with a (parenthesis', 'complete'), ('/preview\n(list 1 2)', 'complete')]
        for i, (text, expected) in enumerate(cases):
            send({'type': 'probe', 'id': i, 'text': text})
            assert until('probe')['status'] == expected
        send({'type': 'submit', 'text': '/status'})
        after = until('view')['view']
        assert (initial['remaining'], initial['generation'], initial['revision']) == (after['remaining'], after['generation'], after['revision'])
        until('input')
        send({'type': 'submit', 'text': '/execute\n(list "🙂" "é" "👩🏽‍💻")'})
        result = until('view')['view']
        assert result['result']['values'][0]['text'] == '("🙂" "é" "👩🏽‍💻")'
        assert result['revision'] == initial['revision']
        until('input')
        send({'type': 'eof'})
        until('exit')
        assert child.wait(timeout=10) == 0
        assert startup['workspace'] == str(store) + '/'
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


def rendering_checks():
    def render(width, no_color):
        output = io.StringIO()
        console = Console(file=output, width=width, force_terminal=True, color_system='256', no_color=no_color)
        renderer = Renderer(console, emoji=False)
        renderer.handle({'type': 'startup', 'data': {'workspace': '/tmp/workspace', 'application': 'test', 'model': 'test-model', 'commands': []}})
        renderer.handle({'type': 'assistant', 'data': {'text': '# Result\n**Accepted**\n```lisp\n(list "🙂")\n```'}})
        renderer.handle({'type': 'context', 'data': {'phase': 'compacted', 'input_tokens': 12000,
                         'context_tokens': 65536, 'compact_threshold': 45875, 'compactions': 2, 'backend': 'summary'}})
        renderer.handle({'type': 'view', 'data': {'view': {'status': 'paused', 'condition': 'Oops\x1b[31m\u202e',
                         'revision': 'revision-1', 'restarts': [{'id': '1/0', 'name': 'USE', 'report': 'Resume'}], 'result': {}}, 'detail': False}})
        renderer.handle({'type': 'view', 'data': {'command': '/execute', 'view': {'operation_id': 'op-1',
                         'result': {'commit': 'accepted', 'values': [{'text': '"🙂"', 'truncated': True}], 'changed': False}}}})
        renderer.handle({'type': 'error', 'data': {'text': '[bold red]literal[/bold red]\x1b]0;unsafe\x07'}})
        return output.getvalue()
    for width in (35, 100):
        text = render(width, True)
        plain = ANSI.sub(b'', text.encode()).decode()
        assert 'Live call paused' in plain and '1/0' in plain and '🙂' in plain
        assert '\\u{001B}' in plain and '\\u{202E}' in plain and '[bold red]' in plain
        assert 'truncated' in plain and 'no new revision' in plain
        assert 'Context compacted' in plain and 'estimated' in plain and '2 compactions' in plain
        assert not re.search(r'\x1b\[(?:38|48|3[0-7]|4[0-7]);?', text), text


def history_property(directory):
    random_source = random.Random(424242)
    trace = []
    path = directory / 'history'
    path.mkdir()
    history = WorkspaceHistory(path)
    try:
        for _ in range(100):
            entry = ''.join(random_source.choice(['a', '🙂', 'é', '👩🏽‍💻', 'ש', '\n', '\t']) for _ in range(random_source.randrange(1, 40)))
            if not entry.strip():
                continue
            history.append_string(entry)
            history.append_string(entry)
            if not trace or entry != trace[-1]:
                trace.append(entry)
        assert list(WorkspaceHistory(path).load_history_strings()) == list(reversed(trace))
        assert (path / 'input-history.txt').stat().st_mode & 0o777 == 0o600
        assert safe_text('\x1b\u202e🙂é') == '\\u{001B}\\u{202E}🙂é'
    except AssertionError:
        # The minimized reproducer is the shortest failing history prefix.
        small = []
        for entry in trace:
            small.append(entry)
            replay = directory / 'shrink-history'
            replay.mkdir(exist_ok=True)
            (replay / 'input-history.txt').unlink(missing_ok=True)
            h = WorkspaceHistory(replay)
            for value in small:
                h.append_string(value)
            if list(h.load_history_strings()) != list(reversed(small)):
                break
        failure = ROOT / '.image-agent/terminal-history-failure.json'
        failure.parent.mkdir(exist_ok=True)
        failure.write_text(json.dumps({'seed': 424242, 'trace': small, 'original': trace}, ensure_ascii=False))
        raise AssertionError(f'History property failed; replay with python3 tests/terminal_scenarios.py --replay {failure}')


def run():
    with tempfile.TemporaryDirectory(prefix='jiti-terminal-') as name:
        directory = Path(name)
        bridge_checks(directory)
        rendering_checks()
        history_property(directory)
        store = directory / 'application'
        terminal = Terminal(store, directory)
        try:
            terminal.command('/mode lisp', 'Input mode: lisp')
            terminal.send('(list 1 2)\x1b[D\x1b[D\x1b[3~3\r')
            terminal.expect('(1 3)')
            terminal.pump(.2)
            terminal.send('\x1b[A\x1b[D\x1b[D\x1b[3~4\r')
            terminal.expect('(1 4)')
            terminal.pump(.2)
            # One editable multiline buffer: edit an earlier row before submitting.
            terminal.send('(list\r  1\x1b\r  2)\x1b[A\x1b[D\x1b[3~9\r')
            terminal.expect('(9 2)')
            terminal.pump(.2)
            before = (store / 'CURRENT').read_text()
            terminal.send('\x1b[200~(list "🙂" "é" "👩🏽‍💻")\x1b[201~')
            assert (store / 'CURRENT').read_text() == before
            terminal.send('\r')
            terminal.expect('("🙂" "é" "👩🏽‍💻")')
            terminal.pump(.2)
            terminal.send('(setf (gethash :x *state*) 99)\x03')
            terminal.command('/status', 'Application status')
            assert (store / 'CURRENT').read_text() == before
            terminal.command('/functions', 'Functions')
            terminal.command('/describe counter', 'COUNTER')
            terminal.command('/operations', 'Recent operations')
            terminal.command('/help', 'Paste never submits')
            terminal.command('/develop (defun removable () 5)', 'Accepted managed change')
            terminal.command("/develop (fmakunbound 'removable)", 'Accepted managed change')
            terminal.command('/describe removable', 'Function not found')
            # Interrupting the frontend while a call runs must not unwind SBCL.
            start = len(terminal.output)
            terminal.send('/execute (progn (sleep 0.7) (list 73))\r')
            os.kill(terminal.pid, signal.SIGINT)
            terminal.expect('(73)', start=start)
            terminal.command('/status', 'Application status')
            terminal.send('/execute (progn (setf (gethash :x *state*) 99) (restart-case (error "pause") (use () 42)))\r')
            terminal.expect('Live call paused')
            terminal.send('draft\x03')
            terminal.command('/status', 'Live call paused')
            terminal.close()
        finally:
            terminal.close()
        entries = list(WorkspaceHistory(store).load_history_strings())
        assert '(list\n  9\n  2)' in entries, entries
        assert '(setf (gethash :x *state*) 99)' not in entries
        assert not any(entry == 'draft' for entry in entries)
        # Recovered history remains editable. Draft survives a round trip through history.
        restarted = Terminal(store, directory, extra=('--no-emoji',), width=45, environment={'NO_COLOR': '1'})
        try:
            restarted.expect('recovered')
            restarted.command('/mode lisp', 'Input mode: lisp')
            restarted.send('(list 11)\x1b[A\x1b[B\r')
            restarted.expect('(11)')
            restarted.pump(.2)
            restarted.send('\x1b[A\r')
            restarted.expect('(11)')
            restarted.command('/execute (list "again")', '("again")')
            fcntl.ioctl(restarted.fd, termios.TIOCSWINSZ, struct.pack('HHHH', 30, 32, 0, 0))
            os.kill(restarted.pid, signal.SIGWINCH)
            restarted.command('/status', 'Application status')
            restarted.close()
        finally:
            restarted.close()
        # Unexpected worker death wakes the editor and reports recoverable failure.
        broken = Terminal(store, directory)
        try:
            broken.expect('recovered')
            children = Path(f'/proc/{broken.pid}/task/{broken.pid}/children').read_text().split()
            assert len(children) == 1, children
            os.kill(int(children[0]), signal.SIGKILL)
            broken.expect('Backend stopped unexpectedly')
            broken.close(eof=False, expected=2)
        finally:
            broken.close(eof=False, expected=2)
        plain = subprocess.run([sys.executable, 'scripts/repl.py', '--legacy', '--plain', '--store', str(store)],
                               cwd=ROOT, input='/status\n/quit\n', text=True, capture_output=True, timeout=20)
        assert plain.returncode == 0 and 'X . 0' in plain.stdout and '\x1b' not in plain.stdout, plain.stdout + plain.stderr
    print('Terminal: real PTY editing, multiline history, paste, Unicode, pauses, recovery, rendering, probes, and plain mode passed')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--replay':
        record = json.loads(Path(sys.argv[2]).read_text())
        with tempfile.TemporaryDirectory() as directory:
            history = WorkspaceHistory(directory)
            for entry in record['trace']:
                history.append_string(entry)
            assert list(history.load_history_strings()) == list(reversed(record['trace']))
        print('History replay passed')
    else:
        run()
