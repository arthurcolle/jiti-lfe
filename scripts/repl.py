#!/usr/bin/env python3
"""Start the SBCL application, or explicitly select the experimental LFE backend."""
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
if __name__ == '__main__':
    arguments = sys.argv[1:]
    if '--lfe' not in arguments:
        if '--legacy' in arguments:
            arguments.remove('--legacy')
        legacy = Path(__file__).resolve().with_name('legacy_repl.py')
        os.execv(sys.executable, [sys.executable, '-B', str(legacy), *arguments])
    arguments.remove('--lfe')
    from lfe_repl import main
    sys.exit(main(arguments))
