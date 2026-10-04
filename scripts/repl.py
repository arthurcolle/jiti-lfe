#!/usr/bin/env python3
"""Start the loaded Lisp REPL using explicit or local Underclass settings."""
import os
from pathlib import Path
import sys
from local_openai import configure

configure()
loader = Path(__file__).resolve().with_name('repl.lisp')
os.execvp('sbcl', ['sbcl', '--noinform', '--script', str(loader), *sys.argv[1:]])
