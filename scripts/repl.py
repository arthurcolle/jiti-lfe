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
    from lfe_repl import main
    sys.exit(main(arguments))
