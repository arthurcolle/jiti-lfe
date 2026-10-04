#!/usr/bin/env python3
"""Exercise the actual CLI executable boundary in fresh SBCL processes."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
launcher = [sys.executable, str(root / 'scripts/repl.py')]

def run(args, text, env=None, code=0):
    result = subprocess.run([*launcher, *args], input=text, text=True, capture_output=True,
                            cwd=root, env=env, timeout=60)
    assert result.returncode == code, result.stdout + result.stderr
    return result.stdout

with tempfile.TemporaryDirectory(prefix='image-cli-scenarios-') as directory:
    base = Path(directory)
    store = base / 'demo'
    env = os.environ.copy()
    env['HOME'] = str(base)
    for name in ('OPENAI_MODEL', 'OPENAI_API_KEY', 'OPENAI_API_KEY_FILE', 'OPENAI_BASE_URL'):
        env.pop(name, None)
    first = run(['--store', str(store)], '/mode lisp\n(setf (gethash :x *state*) 4)\n'
                '(progn (setf (gethash :x *state*) 99) (error "paused"))\n', env)
    assert 'PAUSED' in first and 'X . 99' in first, first
    recovered = run(['--store', str(store)], '/status\nHello\n/model demo-model\n/model\n/quit\n', env)
    assert 'X . 4' in recovered and 'X . 99' not in recovered, recovered
    assert 'Chat requires OPENAI_MODEL' in recovered and 'Model: demo-model' in recovered, recovered
    rollback = run(['--store', str(store)], '/rollback previous\n/quit\n', env)
    assert 'ROLLED-BACK' in rollback and 'X . 0' in rollback, rollback
    assert 'X . 0' in run(['--store', str(store)], '/status\n/quit\n', env)
    program = base / 'program.lisp'
    program.write_text('''(in-package :cl-user)
(defun make-cli-world ()
  (list :id "custom" :world (image-agent:make-reference-world :initial '((:x . 42)))))
''')
    custom = run(['--program', str(program), '--store', str(base / 'custom')], '/status\n/quit\n', env)
    assert 'X . 42' in custom, custom
    run(['--program', str(program), '--store', str(store)], '', env, code=2)
    # The store lock is held across input waits and released when the process exits.
    held = subprocess.Popen([*launcher, '--store', str(store)], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=root, env=env)
    try:
        while True:
            line = held.stdout.readline()
            assert line, 'CLI exited before displaying ready state'
            if 'Safety:' in line:
                break
        run(['--store', str(store)], '', env, code=2)
    finally:
        held.communicate('/quit\n', timeout=60)
    assert held.returncode == 0
    config = base / '.codex'
    config.mkdir()
    (config / 'config.toml').write_text('model = "profile-model"\nmodel_provider = "underclass"\n'
                                     '[model_providers.underclass]\nbase_url = "http://127.0.0.1:18080/v1"\n')
    (config / 'underclass-overalls.key').write_text('fake-key-never-send')
    overridden = env.copy()
    overridden.update(OPENAI_MODEL='explicit-model', OPENAI_BASE_URL='http://127.0.0.1:1/v1')
    result = run(['--store', str(store)], '/model\nhello\n/quit\n', overridden)
    assert 'Model: explicit-model' in result and 'Chat requires OPENAI_MODEL' in result, result
print('CLI: loaded program, modes, EOF unwind, recovery, rollback, credentials, and store lock passed')
