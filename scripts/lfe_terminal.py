"""Optional terminal presentation. No evaluator, transport, or state ownership."""
from collections import deque
from pathlib import Path
import json
import os
import time


def decorate(base, clean, preview):
    """Retain raw receipts; only their human presentation changes."""
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.padding import Padding
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.text import Text

    class TerminalOutput(type(base)):
        def __init__(self):
            super().__init__(False)
            self.console = Console(markup=False, highlight=False, no_color='NO_COLOR' in os.environ)
            self.receipts = deque(maxlen=200)
            self.receipt_id = 0
            self.chat_active = False
            self.verbose = False

        def busy(self, label):
            return self.console.status(Text(clean(label), style='dim cyan'), spinner='dots')

        def text(self, text):
            self.console.print(Padding(Markdown(clean(text), hyperlinks=False, code_theme='ansi_dark'), (0, 2)))
            self.console.print()

        def error(self, error):
            self.console.print(Text('  × ' + clean(error), style='red'))

        def tool_result(self, result, op=None, compact=True):
            self.result(result, op=op, compact=compact)

        def result(self, result, op=None, compact=True, record=True):
            if 'revision' not in result:
                self.console.print(Syntax(clean(json.dumps(result, ensure_ascii=False, indent=2)),
                                          'json', theme='ansi_dark', word_wrap=True))
                return
            self.last_result = result
            if record:
                self.receipt_id += 1
                self.receipts.append((self.receipt_id, op or 'result', result))
            failed = isinstance(result.get('data'), dict) and result['data'].get('passed') is False
            status = result['status']
            style = 'dim' if status == 'ok' and not failed else 'yellow' if status == 'paused' else 'red'
            marker = '✓' if status == 'ok' and not failed else '!' if status == 'paused' else '×'
            label = clean((op or 'result').removeprefix('lfe_').replace('_', ' '))
            self.console.print(Text(f"  {marker} {label}  ·  {'check failed' if failed else status}  ·  r{result['revision']}", style=style))
            if result.get('reason'):
                self.console.print(Text('    ' + clean(result['reason']), style=style))
            if status == 'paused':
                self.console.print(Text(f"    Repair #{result.get('token', '?')}: /repair SOURCE → /retry, or /abort", style='yellow'))
            if result.get('preview'):
                self.console.print('    Preview; candidate discarded.', style='cyan')
            if not compact:
                self.console.print(Syntax(clean(json.dumps(result, ensure_ascii=False, indent=2)),
                                          'json', theme='ansi_dark', word_wrap=True))
                self.console.print()
                return
            if self.chat_active and not self.verbose:
                self.console.print(f'    /details {self.receipt_id}', style='dim')
                return
            value = result.get('value_display', result.get('value', ''))
            if result.get('json_available') is True:
                self.console.print(Syntax(preview(json.dumps(json.loads(result['value_json']), ensure_ascii=False, indent=2)),
                                          'json', theme='ansi_dark', word_wrap=True))
            elif value:
                self.console.print(Syntax(preview(value), 'lisp', theme='ansi_dark', word_wrap=True))
            # Named inspections expose structured evidence, rather than the full state map.
            if op in {'open', 'status', 'lfe_status'} and result.get('summary'):
                summary = result['summary']
                self.console.print(f"    {summary['functions']} functions  ·  {summary['state_keys']} state keys  ·  "
                                   f"{summary['safety_checks']} safety checks  ·  {summary['goals']} goals", style='dim')
            for key in ('data', 'functions', 'function', 'plans', 'nodes', 'operations', 'content', 'entries'):
                if key in result:
                    self.console.print(key.replace('_', ' '), style='bold cyan')
                    payload = result[key]
                    if key == 'content':
                        self.console.print(Text(preview(payload)))
                    else:
                        self.console.print(Syntax(preview(json.dumps(payload, ensure_ascii=False, indent=2)),
                                                  'json', theme='ansi_dark', word_wrap=True))
            if result.get('display_truncated'):
                self.console.print('Value view is bounded; inspect a specific field.', style='dim')
            self.console.print()

        def activity(self):
            table = Table(box=None, padding=(0, 2))
            for label in ('Receipt', 'Action', 'Status', 'Revision'):
                table.add_column(label)
            for number, action, result in list(self.receipts)[-20:]:
                table.add_row(str(number), clean(action), clean(result['status']), str(result['revision']))
            self.console.print(table)
            self.console.print('Inspect a full receipt with /details N', style='dim')

    return TerminalOutput()


class TerminalSession:
    """Presentation commands wrap the existing dispatcher without bridge calls."""
    def __init__(self, session, clean, error):
        self.session, self.clean, self.error_type = session, clean, error

    def __getattr__(self, name):
        return getattr(self.session, name)

    def run(self, line):
        command, _, arg = line.strip().partition(' ')
        arg = arg.strip()
        output = self.output
        if command == '/activity' and not arg:
            output.activity()
            return True
        if command == '/details':
            if not arg:
                if output.last_result is None:
                    output.text('No bridge result to display yet.')
                else:
                    output.result(output.last_result, compact=False, record=False)
                return True
            try:
                number = int(arg)
                receipt = next(value for n, _, value in output.receipts if n == number)
            except (ValueError, StopIteration):
                raise self.error_type('Receipt unavailable. Use /activity to see retained receipts.') from None
            output.result(receipt, compact=False, record=False)
            return True
        if command == '/view':
            if arg not in {'quiet', 'verbose'}:
                raise self.error_type('Use /view quiet or /view verbose.')
            output.verbose = arg == 'verbose'
            output.text(f'Tool display: {arg}.')
            return True
        if command == '/model':
            if arg:
                if len(arg) > 128 or any(char.isspace() or ord(char) < 32 for char in arg):
                    raise self.error_type('Use /model NAME with a single model ID.')
                self.options.model = arg
                if self.chat:
                    self.chat.model = arg
            output.text('Model: ' + self.clean(self.model))
            return True
        if command == '/help' and not arg:
            result = self.session.run(line)
            output.text('`/activity` receipts · `/details N` inspect · `/view quiet|verbose` · `/model NAME`')
            return result
        output.chat_active = self.mode == 'chat' and not command.startswith('/')
        started = time.monotonic()
        if output.chat_active:
            from rich.text import Text
            output.console.print(Text('  JITI', style='bold cyan'))
        try:
            return self.session.run(line)
        finally:
            if output.chat_active:
                elapsed = time.monotonic() - started
                output.console.print(f'    {elapsed:.1f}s  ·  /activity for execution receipts', style='dim')
                output.console.print()
            output.chat_active = False

    @property
    def model(self):
        return self.chat.model if self.chat else self.options.model or os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini')


class TerminalInput:
    def __init__(self, session, complete, source_ops, clean):
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import NestedCompleter
        from prompt_toolkit.history import InMemoryHistory
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.lexers import DynamicLexer, PygmentsLexer
        from prompt_toolkit.styles import Style
        from pygments.lexers import CommonLispLexer
        keys = KeyBindings()

        @keys.add('enter')
        def submit(event):
            text = event.current_buffer.text
            command, _, body = text.lstrip().partition(' ')
            source_command = command.startswith('/') and command[1:] in source_ops
            lfe = source_command or (session.mode == 'lfe' and not command.startswith('/'))
            if lfe and not complete(body if source_command else text):
                event.current_buffer.insert_text('\n')
            else:
                event.current_buffer.validate_and_handle()

        @keys.add('escape', 'enter')
        @keys.add('c-o')
        def newline(event):
            event.current_buffer.insert_text('\n')

        commands = {name: None for name in ('/help', '/quit', '/status', '/state', '/state-list', '/functions',
            '/describe', '/jobs', '/job', '/notes', '/note', '/plans', '/plan', '/operations', '/history',
            '/execute', '/develop', '/preview', '/repair', '/retry', '/abort', '/rollback', '/details',
            '/activity', '/clear', '/context', '/compact', '/usage', '/model', '/tool-limit', '/pin', '/unpin',
            '/recall', '/compact-preview', '/compact-undo', '/context-tools', '/context-budget', '/archive-read')}
        commands['/mode'] = {'chat': None, 'lfe': None}
        commands['/view'] = {'quiet': None, 'verbose': None}
        commands['/workspace'] = {name: None for name in ('open', 'use', 'projects', 'tree', 'symbols', 'grep',
                                                        'pin', 'unpin', 'context', 'snapshot', 'diff')}

        def toolbar():
            state = f"r{session.bridge.revision}"
            if session.bridge.token is not None:
                state += f"  repair #{session.bridge.token}"
            model = session.model if session.mode == 'chat' else 'native LFE'
            context = ''
            if session.chat:
                observation = session.chat.context()
                context = f"  {observation['bytes'] / 1024:.0f} KiB  {session.chat.request_count} requests"
            return [('class:toolbar', clean(f' {session.mode.upper()}  {model}  {state}  {Path(session.options.store).name}{context} '))]

        self.session = session
        self.prompt = PromptSession(history=InMemoryHistory(), multiline=True, key_bindings=keys,
            completer=NestedCompleter.from_nested_dict(commands), complete_while_typing=False,
            lexer=DynamicLexer(lambda: PygmentsLexer(CommonLispLexer) if session.mode == 'lfe' else None),
            bottom_toolbar=toolbar, prompt_continuation='  · ', enable_open_in_editor=False,
            style=Style.from_dict({'prompt': 'bold ansicyan', 'toolbar': 'bg:ansiblack ansibrightblack',
                                  'completion-menu.completion.current': 'bg:ansicyan ansiblack'}))

    def read(self):
        return self.prompt.prompt([('class:prompt', '  › ')])

    def banner(self):
        from rich.text import Text
        console = self.session.output.console
        console.print()
        console.print(Text('JITI  /  live Lisp workspace', style='bold cyan'))
        console.print(Text(str(Path(self.session.options.store).expanduser()), style='dim'))
        console.print('Enter send  ·  Alt+Enter newline  ·  Tab commands  ·  Ctrl+R history', style='dim')
        console.print()
