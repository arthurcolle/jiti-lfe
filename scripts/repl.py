#!/usr/bin/env python3
"""Start the live application with terminal editing or a plain pipe interface."""
import os
from pathlib import Path
import sys
from local_openai import configure

configure()
arguments = sys.argv[1:]
plain = '--plain' in arguments
emoji = '--no-emoji' not in arguments
arguments = [argument for argument in arguments if argument not in ('--plain', '--no-emoji')]
interactive = sys.stdin.isatty() and sys.stdout.isatty() and os.environ.get('TERM') != 'dumb'
if plain or not interactive or '--help' in arguments:
    loader = Path(__file__).resolve().with_name('repl.lisp')
    os.execvp('sbcl', ['sbcl', '--noinform', '--script', str(loader), *arguments])
else:
    from terminal_ui import main
    sys.exit(main(arguments, emoji=emoji))
