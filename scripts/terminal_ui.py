"""Terminal presentation and editing; application semantics remain in SBCL."""
import asyncio
import json
import os
from pathlib import Path
import signal
import sys
import subprocess
import threading

from prompt_toolkit import PromptSession
from prompt_toolkit.application import get_app, run_in_terminal
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.processors import HighlightMatchingBracketProcessor
from prompt_toolkit.lexers import DynamicLexer, PygmentsLexer, SimpleLexer
from prompt_toolkit.styles import Style
from prompt_toolkit.output import ColorDepth
from pygments.lexers import CommonLispLexer
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

BIDI_CONTROLS = {0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)}


def safe_text(value):
    "Escape display controls without normalizing text or changing submitted input."
    text = str(value if value is not None else '')
    return ''.join(f'\\u{{{ord(c):04X}}}'
                   if (ord(c) < 32 and c not in '\n\t') or 127 <= ord(c) < 160 or ord(c) in BIDI_CONTROLS
                   else c for c in text)


class WorkspaceHistory(FileHistory):
    def __init__(self, workspace):
        path = Path(workspace) / 'input-history.txt'
        descriptor = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            os.fchmod(descriptor, 0o600)
        finally:
            os.close(descriptor)
        super().__init__(str(path))
        self.last = next(iter(self.load_history_strings()), None)

    def append_string(self, string):
        if string.strip() and string != self.last:
            super().append_string(string)
            self.last = string


class Renderer:
    def __init__(self, console=None, emoji=True):
        self.console = console or Console(no_color='NO_COLOR' in os.environ,
                                          theme=Theme({'accent': 'cyan', 'good': 'green', 'warn': 'yellow',
                                                       'bad': 'red', 'quiet': 'bright_black'}))
        self.emoji = emoji
        self.mode = 'chat'
        self.view = {}
        self.model = None
        self.context = {}
        self.workspace = None
        self.commands = []
        self.spinner = None
        self.last_result = None
        self.closed = False

    def icon(self, unicode, plain):
        return unicode if self.emoji else plain

    def line(self, text, style=None):
        self.console.print(Text(safe_text(text), style=style or ''))

    def busy(self, text='Running application'):
        text = safe_text(text)
        if self.spinner:
            self.spinner.update(text)
        elif self.console.is_terminal:
            self.spinner = self.console.status(Text(text, style='cyan'), spinner='dots')
            self.spinner.start()

    def ready(self):
        if self.spinner:
            self.spinner.stop()
            self.spinner = None

    def toolbar(self):
        state = self.view.get('status', 'starting')
        revision = self.view.get('revision_number') or '—'
        budget = self.view.get('remaining', '—')
        width = get_app().output.get_size().columns
        text = f' {self.mode}  ·  revision {revision}  ·  {state}'
        if width >= 85 and self.context:
            used, total = self.context.get('input_tokens', 0), self.context.get('context_tokens', 1)
            text += f'  ·  context ~{round(100 * used / max(1, total))}%'
        if width >= 65:
            text += f'  ·  {budget} actions  |  Enter submit · Alt+Enter newline · /help'
        return FormattedText([('class:toolbar', safe_text(text[:max(1, width - 1)]))])

    def handle(self, event):
        kind, data = event['type'], event.get('data', {})
        if kind == 'startup':
            self.workspace, self.model = data['workspace'], data.get('model')
            self.commands = data.get('commands', [])
            content = Text()
            content.append(safe_text(data['application']), style='bold cyan')
            content.append('  ·  ' + ('recovered' if data.get('recovered') else 'new workspace'), style='green')
            content.append('\nModel      ', style='dim')
            content.append(safe_text(self.model or 'not configured — /model NAME'))
            content.append('\nWorkspace  ', style='dim')
            content.append(safe_text(self.workspace))
            content.append('\n\nPrompt to build. Compose to execute. /help to explore.', style='dim')
            self.console.print(Panel(content, title=self.icon('✨ jiti', 'jiti'), border_style='cyan', expand=False))
        elif kind == 'view':
            self.view = data['view']
            self.render_view(data)
        elif kind == 'assistant':
            self.console.print(Text(self.icon('💬 Assistant', 'Assistant'), style='bold cyan'))
            self.console.print(Markdown(safe_text(data.get('text', '')), hyperlinks=False))
            self.console.print()
        elif kind == 'tool':
            name, result = data.get('name', ''), data.get('result') or {}
            outcome = result.get('result') or {}
            label = name.replace('_', ' ')
            if result.get('error'):
                self.line(f'{label}: {result["error"]}', 'yellow')
            elif result.get('status') == 'paused':
                self.line(f'{label}: paused — live restarts available', 'yellow')
            elif outcome.get('commit'):
                detail = 'managed changes accepted' if outcome.get('changed') else 'no managed change'
                if outcome.get('commit') == 'restored':
                    detail = 'managed state restored'
                self.line(f'{label}: {detail}', 'dim')
                self.render_result(result)
            else:
                self.line(label, 'dim')
        elif kind == 'history':
            table = Table(title='Application revisions', expand=True, show_lines=False)
            table.add_column('#', style='cyan', no_wrap=True)
            table.add_column('Revision')
            table.add_column('Parent', style='dim')
            table.add_column('Rollback source', style='yellow')
            for record in data.get('revisions', []):
                table.add_row(str(record['number']), safe_text(record['id']), safe_text(record.get('parent')),
                              safe_text(record.get('rollback_source')))
            self.console.print(table)
        elif kind == 'help':
            table = Table(title='Commands', expand=True)
            table.add_column('Command', style='cyan')
            table.add_column('Purpose')
            for command in data.get('commands', []):
                table.add_row(command['command'] + ' ' + command['arguments'], safe_text(command['description']))
            self.console.print(table)
            self.console.print(Panel(Text('Arrows edit; Up/Down recall complete submissions at buffer boundaries.\n'
                                          'Enter submits complete input. Alt+Enter (or Esc, Enter) inserts a newline.\n'
                                          'Ctrl+C clears input. Ctrl+D exits an empty buffer.\n'
                                          'Paste never submits. Input history is saved privately per workspace.\n'
                                          '/history lists revisions; /abort restores a paused attempt.\n'
                                          'Preview restores managed effects, not external I/O.'), title='Editing', border_style='cyan'))
        elif kind == 'mode':
            self.mode = data['mode']
            self.line(f'Input mode: {self.mode}', 'cyan')
        elif kind == 'model':
            self.model = data.get('model')
            self.line(f'Model: {self.model or "not configured — /model NAME"}', 'cyan')
        elif kind == 'context':
            self.context = data
            phase = data.get('phase', 'status')
            if phase == 'compacting':
                self.busy('Compacting conversation; live worker preserved')
            elif phase == 'failed':
                self.ready()
                self.line('Compaction failed; conversation and live world preserved. Retry /compact or inspect /context.', 'yellow')
            elif phase != 'usage':
                self.ready()
                self.line(f'Context {phase}: ~{data.get("input_tokens", 0):,}/{data.get("context_tokens", 0):,} tokens '
                          f'(estimated) · threshold {data.get("compact_threshold", 0):,} · '
                          f'{data.get("compactions", 0)} compactions · {data.get("backend", "none")}', 'cyan')
                if phase == 'status' and data.get('last_request_tokens'):
                    self.line(f'Last request: {data["last_request_tokens"]:,} tokens '
                              f'({data.get("last_request_counting", "estimated")}).', 'dim')
        elif kind == 'busy':
            self.busy(data.get('text', 'Working'))
        elif kind in ('error', 'diagnostic'):
            self.line(f'{self.icon("⚠️", "!")} {data.get("text", "Backend failed")}', 'red' if kind == 'error' else 'dim')
        elif kind == 'exit':
            self.ready()
            self.closed = True
            self.line(self.icon('👋 ', '') + data.get('text', 'Application closed.'), 'dim')
        elif kind == 'output':
            self.line(data.get('text', ''))

    def render_result(self, view):
        result = view.get('result') or {}
        commit = result.get('commit')
        identity = (view.get('operation_id'), commit, result.get('reason'))
        if not commit or identity == self.last_result:
            return
        self.last_result = identity
        if commit == 'accepted':
            label = 'Accepted managed change' if result.get('changed') else 'Executed · no new revision'
            style, icon = 'green', self.icon('✓', '+')
        elif commit == 'rolled-back':
            label, style, icon = 'Rollback published a new revision', 'green', self.icon('↩', '<-')
        else:
            label, style, icon = ('Preview · managed state restored' if result.get('reason') == 'PREVIEW'
                                  else 'Managed state restored'), 'yellow', self.icon('↩', '<-')
        self.line(f'{icon} {label}', style)
        for value in result.get('values', []):
            self.console.print(Syntax(safe_text(value['text']), 'common-lisp', theme='ansi_dark',
                                      word_wrap=True, background_color='default'))
            if value.get('truncated'):
                self.line('… value truncated', 'yellow')
            if value.get('print_error'):
                self.line('Value could not be fully printed', 'yellow')
        if result.get('values_truncated'):
            self.line(f'… showing a bounded subset of {result.get("value_count", 0)} returned values', 'yellow')
        if commit == 'restored' and result.get('reason'):
            self.line('Reason: ' + str(result['reason']), 'dim')

    def render_view(self, data):
        view, command = data['view'], data.get('command')
        result = view.get('result') or {}
        if data.get('detail'):
            self.console.print(Panel(Group(
                Text(f'State: {view.get("status")}   Revision: {view.get("revision_number")}   '
                     f'Generation: {view.get("generation")}   Budget: {view.get("remaining")}'),
                Text(safe_text(view.get('revision')), style='dim'),
                Syntax(safe_text(view.get('world', '')), 'common-lisp', theme='ansi_dark', word_wrap=True,
                       background_color='default')), title='Application status', border_style='cyan'))
            for category, checks in [('Goals', view.get('goal_checks', [])), ('Safety', view.get('safety_checks', []))]:
                for check in checks:
                    self.line(f'{category}: {check["name"]} — {check["status"]}',
                              'green' if check['status'] == 'PASS' else 'red')
        elif command == '/functions':
            table = Table(title=f'Functions · {result.get("catalogue_count", 0)} available', expand=True)
            table.add_column('Name', style='cyan')
            table.add_column('Arguments')
            table.add_column('Documentation', style='dim')
            for entry in result.get('functions', []):
                table.add_row(safe_text(entry['name']), safe_text(entry.get('arguments')),
                              safe_text(entry.get('documentation')) + (' …' if entry.get('documentation_truncated') else ''))
            self.console.print(table)
            if result.get('next_offset') is not None:
                self.line(f'Next page: /functions {result["next_offset"]}', 'dim')
        elif command == '/describe':
            entry = result.get('function_info')
            if entry:
                self.line(f'{entry["name"]} {entry.get("arguments", "")}', 'bold cyan')
                if entry.get('documentation'):
                    self.line(entry['documentation'])
                self.console.print(Syntax(safe_text(entry.get('source', '')), 'common-lisp', theme='ansi_dark',
                                          word_wrap=True, background_color='default'))
                if entry.get('source_truncated'):
                    self.line('… source truncated', 'yellow')
            else:
                self.line('Function not found in the managed catalogue', 'yellow')
        elif command == '/operations':
            table = Table(title='Recent operations', expand=True)
            for title in ('Operation', 'Intent', 'Outcome', 'Source'):
                table.add_column(title, style='cyan' if title == 'Intent' else None)
            for record in result.get('operation_records', []):
                intent = record['intent'].lower() + (' · preview' if record.get('preview') else '')
                table.add_row(safe_text(record['id']), intent, safe_text(record['status']).lower(),
                              safe_text(record.get('source')) + (' …' if record.get('source_truncated') else ''))
            self.console.print(table)
            if result.get('operations_truncated'):
                self.line('… showing recent operations; complete diagnostic history remains in the journal', 'dim')
        else:
            self.render_result(view)
        if view.get('status') == 'paused':
            lines = [Text(safe_text(view.get('condition')), style='yellow')]
            for index, restart in enumerate(view.get('restarts', []), 1):
                lines.append(Text(f'{index}. {safe_text(restart.get("name") or "unnamed")}  '
                                  f'[{safe_text(restart["id"])}]\n   {safe_text(restart.get("report"))}'))
            lines.append(Text('Ask to repair or resume a restart. /abort restores the attempt.', style='dim'))
            self.console.print(Panel(Group(*lines), title=self.icon('⏸ Live call paused', 'Live call paused'), border_style='yellow'))
        elif view.get('status') in ('faulted', 'exhausted', 'aborted'):
            self.line(f'Worker {view["status"]}. Quit and reopen to recover accepted revisions.', 'red')
        if view.get('rejected') and view['rejected'] != 'NIL':
            self.line('Action rejected: ' + str(view['rejected']), 'yellow')


class TerminalApp:
    def __init__(self, arguments, emoji=True):
        self.arguments = arguments
        self.renderer = Renderer(emoji=emoji)
        self.process = None
        self.inputs = asyncio.Queue()
        self.pending = {}
        self.probe_counter = 0
        self.session = None
        self.mode = 'chat'
        self.notice = ''
        self.active = False
        self.tasks = []
        self.events = asyncio.Queue()
        self.write_lock = threading.Lock()
        self.readers = []

    def write(self, message):
        if self.process.poll() is not None:
            raise EOFError('Backend stopped')
        with self.write_lock:
            self.process.stdin.write((json.dumps(message, ensure_ascii=False) + '\n').encode('utf-8'))
            self.process.stdin.flush()

    async def send(self, message):
        self.write(message)

    def probe(self, text):
        # Classify before consuming the next key. A reader thread handles the reply,
        # so fast typing after Enter cannot race ahead of its newline/submission.
        self.probe_counter += 1
        identifier = self.probe_counter
        ready, response = threading.Event(), {}
        self.pending[identifier] = (ready, response)
        try:
            self.write({'type': 'probe', 'id': identifier, 'text': text})
            if not ready.wait(5):
                raise TimeoutError('Reader probe timed out')
            if response.get('error'):
                raise EOFError('Backend stopped')
            return response['status']
        finally:
            self.pending.pop(identifier, None)

    def collect(self, stream, loop, diagnostic=False):
        def enqueue(event):
            try:
                loop.call_soon_threadsafe(self.events.put_nowait, event)
            except RuntimeError:
                pass
        try:
            while line := stream.readline(1048577):
                if len(line) > 1048576:
                    raise ValueError('Backend message exceeds limit')
                if diagnostic:
                    enqueue({'type': 'diagnostic', 'data': {'text': line.decode('utf-8', errors='replace').rstrip('\n')}})
                    continue
                event = json.loads(line)
                if event['type'] == 'probe':
                    data = event['data']
                    pending = self.pending.get(data['id'])
                    if pending:
                        ready, response = pending
                        response['status'] = data['status']
                        ready.set()
                else:
                    enqueue(event)
        except (ValueError, KeyError, OSError):
            enqueue({'type': 'error', 'data': {'text': 'Invalid backend protocol. Accepted revisions remain recoverable.'}})
        finally:
            if not diagnostic:
                for ready, response in list(self.pending.values()):
                    response['error'] = True
                    ready.set()
                enqueue(None)

    async def display(self, event):
        if self.active:
            await run_in_terminal(lambda: self.renderer.handle(event))
        else:
            self.renderer.handle(event)
        if self.session and self.session.app.is_running:
            self.session.app.invalidate()

    async def receive(self):
        try:
            while (event := await self.events.get()) is not None:
                if event['type'] == 'input':
                    self.renderer.ready()
                    await self.inputs.put(event['data'])
                else:
                    await self.display(event)
        finally:
            # A failed renderer must wake the input loop as well as a dead backend.
            await self.inputs.put(None)
            if self.active and self.session.app.is_running:
                self.session.app.exit(exception=EOFError())

    def bindings(self):
        bindings = KeyBindings()

        @bindings.add('up')
        def up(event):
            buffer = event.current_buffer
            if buffer.document.cursor_position_row:
                buffer.cursor_up()
            else:
                buffer.history_backward()

        @bindings.add('down')
        def down(event):
            buffer = event.current_buffer
            if buffer.document.cursor_position_row < buffer.document.line_count - 1:
                buffer.cursor_down()
            else:
                buffer.history_forward()

        @bindings.add('escape', 'enter')
        def newline(event):
            event.current_buffer.insert_text('\n')

        @bindings.add('c-c')
        def clear(event):
            event.current_buffer.reset()
            self.notice = 'Input cleared — application state unchanged'
            event.app.invalidate()

        @bindings.add('c-d')
        def eof(event):
            if not event.current_buffer.text:
                event.app.exit(exception=EOFError())
            else:
                event.current_buffer.delete()

        @bindings.add('enter')
        def enter(event):
            buffer = event.current_buffer
            text, cursor = buffer.text, buffer.cursor_position
            if len(text) > 16384:
                self.notice = 'Input exceeds the 16,384 character limit'
                event.app.invalidate()
                return
            try:
                status = self.probe(text)
            except TimeoutError:
                self.notice = 'Reader probe timed out; input preserved'
                event.app.invalidate()
                return
            except EOFError:
                if not event.app.is_done:
                    event.app.exit(exception=EOFError())
                return
            if event.app.is_done or buffer.text != text or buffer.cursor_position != cursor:
                return
            if status == 'incomplete':
                buffer.insert_text('\n')
            else:
                buffer.validate_and_handle()

        return bindings

    def is_lisp(self):
        text = self.session.default_buffer.text.lstrip() if self.session else ''
        command = text.split(None, 1)[0] if text else ''
        return command in ('/develop', '/execute', '/preview') or (self.mode == 'lisp' and not text.startswith('/'))

    def footer(self):
        return self.notice or self.renderer.toolbar()

    def make_session(self):
        no_color = 'NO_COLOR' in os.environ
        style = Style.from_dict({} if no_color else {
            'prompt': 'ansicyan bold', 'muted': 'ansibrightblack',
            'toolbar': 'bg:ansiblack ansibrightblack',
            'matching-bracket.other': 'ansiyellow bold', 'matching-bracket.cursor': 'ansiyellow bold',
        })
        history = WorkspaceHistory(self.renderer.workspace)
        self.session = PromptSession(
            history=history, multiline=True, key_bindings=self.bindings(), style=style,
            lexer=DynamicLexer(lambda: PygmentsLexer(CommonLispLexer) if self.is_lisp() and not no_color else SimpleLexer()),
            input_processors=[HighlightMatchingBracketProcessor(chars='()[]{}')],
            bottom_toolbar=self.footer, complete_while_typing=False,
            completer=WordCompleter([entry['command'] for entry in self.renderer.commands], sentence=True),
            enable_history_search=False, color_depth=ColorDepth.DEPTH_1_BIT if no_color else None,
        )

    def interrupt(self):
        if not self.active:
            self.renderer.line('Still running. The live worker is protected; use /abort when a paused call returns.', 'yellow')

    async def run(self):
        loader = Path(__file__).resolve().with_name('terminal.lisp')
        self.process = subprocess.Popen(
            ['sbcl', '--noinform', '--script', str(loader), *self.arguments],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
        )
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, self.interrupt)
        for stream, diagnostic in ((self.process.stdout, False), (self.process.stderr, True)):
            thread = threading.Thread(target=self.collect, args=(stream, loop, diagnostic), daemon=True)
            thread.start()
            self.readers.append(thread)
        self.tasks = [asyncio.create_task(self.receive())]
        self.renderer.busy('Loading the application')
        try:
            while request := await self.inputs.get():
                if self.session is None:
                    self.make_session()
                self.mode = self.renderer.mode = request['mode']
                self.notice = ''
                self.active = True
                initial = (request.get('initial') or '') + ('\n' if request.get('continuation') else '')
                try:
                    text = await self.session.prompt_async(
                        FormattedText([('class:prompt', self.mode), ('class:muted', ' › ')]), default=initial)
                except EOFError:
                    self.active = False
                    if self.process.poll() is None:
                        await self.send({'type': 'eof'})
                    break
                finally:
                    self.active = False
                await self.send({'type': 'submit', 'text': text})
                self.renderer.busy()
            await asyncio.wait_for(asyncio.to_thread(self.process.wait), 10)
            await asyncio.gather(*self.tasks)
            if not self.renderer.closed:
                self.renderer.line('Backend stopped unexpectedly. Reopen the workspace to recover accepted revisions.', 'red')
                return 2
            return self.process.returncode or 0
        finally:
            self.renderer.ready()
            if self.process.poll() is None:
                self.process.stdin.close()
                try:
                    await asyncio.wait_for(asyncio.to_thread(self.process.wait), 5)
                except asyncio.TimeoutError:
                    self.process.terminate()
                    try:
                        await asyncio.wait_for(asyncio.to_thread(self.process.wait), 5)
                    except asyncio.TimeoutError:
                        self.process.kill()
                        await asyncio.to_thread(self.process.wait)
            for task in self.tasks:
                task.cancel()
            await asyncio.gather(*self.tasks, return_exceptions=True)
            loop.remove_signal_handler(signal.SIGINT)
            for reader in self.readers:
                reader.join(timeout=1)
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                stream.close()


def main(arguments, emoji=True):
    try:
        return asyncio.run(TerminalApp(arguments, emoji=emoji).run())
    except (OSError, ValueError, asyncio.TimeoutError):
        print('Terminal frontend stopped. Reopen the workspace to recover accepted revisions.', file=sys.stderr)
        return 2
