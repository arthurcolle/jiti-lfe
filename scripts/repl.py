#!/usr/bin/env python3
"""Start the LFE fork; explicitly select the inherited SBCL backend with --legacy."""
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
if __name__ == '__main__':
    arguments = sys.argv[1:]
    if '--lfe' in arguments and '--legacy' in arguments:
        sys.exit('--lfe and --legacy select different backends; choose one')
    if '--legacy' in arguments:
        arguments.remove('--legacy')
        legacy = Path(__file__).resolve().with_name('legacy_repl.py')
        os.execv(sys.executable, [sys.executable, '-B', str(legacy), *arguments])
    if '--lfe' in arguments:
        arguments.remove('--lfe')
    # Use the optional repo-local terminal environment only for a real terminal.
    # Batch/JSON clients and the legacy backend keep their original interpreter.
    ui_python = Path(__file__).resolve().parents[1] / '.jiti/ui-venv/bin/python'
    if (sys.stdin.isatty() and sys.stdout.isatty()
            and not any(flag in arguments for flag in ('--plain', '--json', '--eval'))
            and ui_python.is_file() and Path(sys.prefix) != ui_python.parent.parent):
        os.execv(str(ui_python), [str(ui_python), '-B', str(Path(__file__).resolve()), *arguments])
    from lfe_repl import main
    sys.exit(main(arguments))
