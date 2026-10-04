#!/usr/bin/env python3
"""Launch bounded live evolution (or offline replay) with an external watchdog."""
import os
from pathlib import Path
import subprocess
import sys
from local_openai import configure

configure()
script = Path(__file__).resolve().with_name('experiment.lisp')
try:
    result = subprocess.run(['sbcl', '--noinform', '--script', str(script), *sys.argv[1:]], timeout=600)
except subprocess.TimeoutExpired:
    print('Evolution stopped: the 600-second watchdog expired. Accepted revisions remain in the experiment workspace.', file=sys.stderr)
    sys.exit(124)
sys.exit(result.returncode)
