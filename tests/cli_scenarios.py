#!/usr/bin/env python3
"""Exercise the actual CLI executable boundary in fresh SBCL processes."""
import os
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

root = Path(__file__).resolve().parents[1]
launcher = [sys.executable, str(root / 'scripts/repl.py'), '--legacy']

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
    context = run(['--store', str(store), '--context-tokens', '32768', '--compact-threshold', '22000'],
                  '/context\n/compact\n/context clear\n/quit\n', env)
    assert '32768 tokens' in context and 'No conversation memory to compact' in context, context
    run(['--store', str(store), '--context-tokens', '32768', '--compact-threshold', '32000'], '', env, code=2)
    # Exercise the actual HTTP transport's streamed error body and compact-and-retry path.
    counts = {'normal': 0, 'compact': 0, 'summary': 0}

    class ContextProvider(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            status = 200
            if self.path.endswith('/compact'):
                counts['compact'] += 1
                status, payload = 404, {'error': {'code': 'unsupported_endpoint'}}
            elif request.get('instructions', '').startswith('Summarize this conversation'):
                counts['summary'] += 1
                assert 'tools' not in request
                payload = {'goal': ['Continue'], 'constraints': [], 'decisions': [],
                           'verified_progress': ['First reply completed'], 'unfinished_work': ['Continue']}
                payload = self.completed(json.dumps(payload))
            else:
                counts['normal'] += 1
                if counts['normal'] == 1:
                    payload = self.completed('a' * 22000)
                elif counts['normal'] == 2:
                    status, payload = 400, {'error': {'code': 'context_length_exceeded', 'message': 'private-error-body'}}
                else:
                    assert request['input'][-1]['content'] == 'Continue'
                    payload = self.completed('Recovered after compaction.')
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            payload = payload.encode()
            self.send_response(status)
            self.send_header('Content-Type', 'text/event-stream' if status == 200 else 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        @staticmethod
        def completed(text):
            return 'data: ' + json.dumps({'type': 'response.completed', 'response': {
                'status': 'completed', 'usage': {'input_tokens': 100}, 'output': [
                    {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': text}]}]}}) + '\n\n'

    provider = ThreadingHTTPServer(('127.0.0.1', 0), ContextProvider)
    provider_thread = threading.Thread(target=provider.serve_forever, daemon=True)
    provider_thread.start()
    try:
        context_env = env.copy()
        context_env.update(OPENAI_MODEL='fake', OPENAI_API_KEY='synthetic-http-key',
                           OPENAI_BASE_URL=f'http://127.0.0.1:{provider.server_port}/v1')
        recovered_context = run(['--store', str(base / 'http-context')],
                                'Begin\nContinue\n/context\n/model changed\n/context\n/quit\n', context_env)
        assert 'Recovered after compaction.' in recovered_context and 'Last request: 100 tokens (reported)' in recovered_context
        assert 'private-error-body' not in recovered_context and 'synthetic-http-key' not in recovered_context
        assert counts == {'normal': 3, 'compact': 1, 'summary': 1}, counts
    finally:
        provider.shutdown()
        provider.server_close()
        provider_thread.join(timeout=5)
    composed_store = base / 'composition'
    composed = run(['--store', str(composed_store)],
                   '/develop (defun twice (x) "Double X." (* x 2))\n'
                   '/execute (twice (twice 3))\n/preview (incf (gethash :x *state*))\n'
                   '/functions\n/describe twice\n/operations\n/history\n/quit\n', env)
    assert ':TEXT "12"' in composed and 'Double X.' in composed, composed
    assert ':REASON :PREVIEW' in composed and ':INTENT :EXECUTE' in composed, composed
    assert 'revision 3 ' not in composed, composed
    recovered_composition = run(['--store', str(composed_store)],
                               '/execute (twice (twice 3))\n/describe twice\n/operations\n/quit\n', env)
    assert ':TEXT "12"' in recovered_composition and 'Double X.' in recovered_composition, recovered_composition
    assert 'revision 3 ' not in recovered_composition, recovered_composition
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
