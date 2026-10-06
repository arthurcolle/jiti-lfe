#!/usr/bin/env python3
"""Actual BEAM catalogue/operation recovery, including a publication fault."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from lfe_repl import Bridge, Chat, FrontendError


@contextmanager
def session(store, **options):
    bridge = Bridge(store, **options)
    try:
        assert bridge.open_result['status'] == 'ok', bridge.open_result
        yield bridge
    finally:
        bridge.close()


def success(bridge, source, op='execute'):
    result = bridge.request(op, source=source)
    assert result['status'] == 'ok', result
    assert result['operation_id'].startswith('operation-'), result
    return result


def records(bridge):
    result = bridge.request('operations')
    assert result['status'] == 'ok', result
    return result['operations']


def catalogue(base):
    store = base / 'catalogue'
    with session(store) as bridge:
        source = '(defun twice (x) "Double x — café." (* x 2))'
        first = success(bridge, source)
        assert first['revision'] == 1
        assert success(bridge, source)['revision'] == 1
        page = bridge.request('functions')
        assert page['function_count'] == 1 and page['next_offset'] is None
        info = page['functions'][0]
        assert info['name'] == 'twice' and info['arity'] == 1 and info['arguments'] == '(x)'
        assert info['documentation'] == 'Double x — café.' and 'source' not in info
        description = bridge.request('describe', name='twice', arity=1)
        assert description['found'] and 'Double x — café.' in description['function']['source']
        assert success(bridge, description['function']['source'])['revision'] == 1
        assert not description['function']['source_truncated']
        success(bridge, '(defun twice (x y) (+ x y)) (defun caller (x) (twice x))')
        success(bridge, '(defun quoted () \'(twice 4))')
        description = bridge.request('describe', name='twice', arity=1)
        assert [entry['name'] for entry in description['callers']] == ['caller']
        assert bridge.request('describe', name='twice', arity=2)['found']
        assert not bridge.request('describe', name='unknown-never-interned', arity=0)['found']
        success(bridge, '(defun factorial ((0) 1) ((n) (* n (factorial (- n 1)))))')
        assert bridge.request('describe', name='factorial', arity=1)['function']['arguments'] == '(0)'
        revision = bridge.revision
        changed_doc = '(defun twice (x) "New docs." (* x 2))'
        assert success(bridge, changed_doc)['revision'] == revision + 1
        assert success(bridge, '(defun twice (x) "Preview." (* x 2))', 'preview')['revision'] == revision + 1
        assert bridge.request('describe', name='twice', arity=1)['function']['documentation'] == 'New docs.'
        assert bridge.request('execute', source='(future 3)')['status'] == 'paused'
        success(bridge, '(defun future (x) "Provisional." (+ x 1))', 'repair')
        assert bridge.request('describe', name='future', arity=1)['found']
        assert bridge.request('abort')['status'] == 'ok'
        assert not bridge.request('describe', name='future', arity=1)['found']
        accepted = bridge.revision
        success(bridge, "(forget 'twice 1)")
        assert not bridge.request('describe', name='twice', arity=1)['found']
        assert bridge.request('describe', name='twice', arity=2)['found']
        assert bridge.request('rollback', revision=accepted)['status'] == 'ok'
        assert bridge.request('describe', name='twice', arity=1)['found']
        # Inspecting functions does not itself create diagnostic operations.
        count = len(records(bridge))
        for _ in range(4):
            bridge.request('functions')
            bridge.request('describe', name='twice', arity=1)
        assert len(records(bridge)) == count
    with session(store) as bridge:
        assert bridge.request('describe', name='twice', arity=1)['function']['documentation'] == 'New docs.'
        success(bridge, '(twice 4)')
        # Execute the model-facing tools locally; no HTTP or credentials needed.
        chat = Chat.__new__(Chat)
        chat.bridge = bridge
        result = chat._tool(dict(name='lfe_describe', arguments='{"name":"twice","arity":1}'))
        assert result['found']
        assert chat._tool(dict(name='lfe_functions', arguments='{"offset":0}'))['function_count'] == 5
        assert chat._tool(dict(name='lfe_operations', arguments='{}'))['operations']
        try:
            chat._tool(dict(name='lfe_describe', arguments='{"name":"twice","arity":true}'))
        except FrontendError:
            pass
        else:
            raise AssertionError('boolean arity accepted')


def diagnostics(base):
    store = base / 'diagnostics'
    marker = 'synthetic-secret-never-in-diagnostics'
    with session(store, safety=["(orelse (=:= (state-get 'x) 'undefined) (>= (state-get 'x) 0))"]) as bridge:
        assert records(bridge) == []
        result = success(bridge, '(+ 2 3)')
        pure_id = result['operation_id']
        assert records(bridge)[0]['status'] == 'completed'
        committed = success(bridge, "(state-put 'x 3)")
        assert records(bridge)[0]['status'] == 'committed'
        assert committed['operation_id'] != pure_id
        success(bridge, "(state-put 'x 8)", 'preview')
        assert records(bridge)[0]['status'] == 'previewed'
        assert bridge.request('execute', source="(state-put 'x -1)")['status'] == 'rejected'
        assert records(bridge)[0]['status'] == 'rejected'
        paused = bridge.request('execute', source='(future 7)')
        operation_id, token = paused['operation_id'], paused['token']
        before = records(bridge)[0]
        assert bridge.request('repair', token=token + 1, source='(defun future (x) x)')['status'] == 'rejected'
        assert records(bridge)[0] == before
        assert success(bridge, '(defun future (x) (+ x 1))', 'repair')['operation_id'] == operation_id
        assert records(bridge)[0]['status'] == 'paused'
        retried = bridge.request('retry')
        assert retried['status'] == 'ok' and retried['operation_id'] == operation_id
        assert records(bridge)[0]['status'] == 'committed' and records(bridge)[0]['steps'] == 3
        paused = bridge.request('execute', source=f'(state-put \'scratch #B("{marker}")) (error #B("{marker}"))')
        interrupted_id = paused['operation_id']
        for path in (store / 'operations').glob('*.json'):
            assert marker not in path.read_text()
            assert path.stat().st_mode & 0o777 == 0o600
        assert (store / 'operations').stat().st_mode & 0o777 == 0o700
        bridge.process.kill()
        bridge.broken = True
    with session(store) as bridge:
        recovered = records(bridge)[0]
        assert recovered['id'] == interrupted_id and recovered['status'] == 'interrupted'
        assert recovered['recovered'] and recovered['goal'] is None
        assert 'token' not in bridge.request('status')
        assert success(bridge, "(state-get 'scratch)")['value'] == 'undefined'
        assert success(bridge, "(state-get 'x)")['value'] == '3'
        paused = bridge.request('execute', source="(error 'cancel)")
        cancelled_id = paused['operation_id']
        # Graceful close explicitly aborts the provisional operation.
    with session(store) as bridge:
        assert records(bridge)[0]['id'] == cancelled_id
        assert records(bridge)[0]['status'] == 'aborted'
    # Failed repairs terminate the original operation, not a second one.
    with session(base / 'failed-repair') as bridge:
        paused = bridge.request('execute', source='(future 1)')
        result = bridge.request('repair', source="(error 'repair_failed)")
        assert result['status'] == 'rejected' and result['operation_id'] == paused['operation_id']
        assert records(bridge)[0]['status'] == 'rejected'
    with session(base / 'timeout', timeout_ms=40) as bridge:
        paused = bridge.request('execute', source="(timer:sleep 5000)")
        assert paused['status'] == 'paused'
        assert records(bridge)[0]['status'] == 'paused'
        assert bridge.request('abort')['status'] == 'ok'


def delayed(bridge, source):
    outcome = []
    def run():
        try:
            outcome.append(bridge.request('execute', source=source))
        except FrontendError as error:
            outcome.append(error)
    thread = threading.Thread(target=run)
    thread.start()
    return thread, outcome


def await_running(store):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        for path in (store / 'operations').glob('*.json'):
            record = json.loads(path.read_text())
            if record['status'] == 'running':
                return path, record
        time.sleep(.01)
    raise AssertionError('operation was not durable before evaluation')


def fault_boundaries(base):
    store = base / 'crash-running'
    with session(store, timeout_ms=5000) as bridge:
        thread, outcome = delayed(bridge, "(timer:sleep 3000) (state-put 'x 99)")
        _, record = await_running(store)
        bridge.process.kill()
        thread.join(5)
        assert not thread.is_alive() and isinstance(outcome[0], FrontendError)
        bridge.broken = True
    with session(store) as bridge:
        assert records(bridge)[0]['id'] == record['id']
        assert records(bridge)[0]['status'] == 'interrupted'
        assert bridge.revision == 0
        assert success(bridge, "(state-get 'x)")['value'] == 'undefined'
    # Force the operation-finish rename to fail AFTER CURRENT publication.
    # This exercises the real controller's uncertain-outcome shutdown.
    store = base / 'publication-window'
    with session(store, timeout_ms=5000) as bridge:
        thread, outcome = delayed(bridge, "(timer:sleep 600) (state-put 'x 7)")
        path, started = await_running(store)
        original = path.read_bytes()
        path.unlink()
        path.mkdir()
        thread.join(5)
        assert not thread.is_alive(), 'publication fault did not terminate request'
        assert outcome[0]['status'] == 'error', outcome
        assert (store / 'CURRENT').read_text() == '1'
        path.rmdir()
        path.write_bytes(original)
        os.chmod(path, 0o600)
    with session(store) as bridge:
        record = records(bridge)[0]
        assert record['id'] == started['id'] and record['status'] == 'committed'
        assert record['revision'] == 1 and record['recovered'] and record['goal'] is None
        assert record['outcome'] == 'published_before_disconnect'
        assert success(bridge, "(state-get 'x)")['value'] == '7'
    # An incomplete temp is ignored; a corrupt published diagnostic fails closed.
    (store / 'operations' / 'orphan.json.123.tmp').write_bytes(b'{')
    with session(store) as bridge:
        assert records(bridge)
    next((store / 'operations').glob('*.json')).write_bytes(b'{')
    bridge = Bridge(store)
    try:
        assert bridge.open_result['status'] == 'error'
    finally:
        bridge.close()


def bounds_and_cli(base):
    store = base / 'bounds'
    with session(store) as bridge:
        success(bridge, '\n'.join(f'(defun f{n:03d} () {n})' for n in range(55)))
        first = bridge.request('functions')
        assert len(first['functions']) == 50 and first['next_offset'] == 50
        tail = bridge.request('functions', offset=50)
        assert len(tail['functions']) == 5 and tail['next_offset'] is None
        assert bridge.request('functions', offset=999)['functions'] == []
        assert bridge.request('functions', offset=-1)['status'] == 'rejected'
        assert bridge.request('describe', name='f000', arity=True)['status'] == 'rejected'
        for n in range(105):
            success(bridge, f'(+ {n} 1)')
        result = bridge.request('operations')
        assert len(result['operations']) == 25 and result['operation_count'] == 100
        assert result['operations_truncated']
    # Recovery must also reconcile files outside the retained inspection window.
    paths = list((store / 'operations').glob('*.json'))
    oldest = min(paths, key=lambda path: json.loads(path.read_text())['started_at'])
    record = json.loads(oldest.read_text())
    record.update(started_at=0, status='running')
    oldest.write_text(json.dumps(record))
    with session(store) as bridge:
        assert bridge.request('operations')['operation_count'] == 100
        assert json.loads(oldest.read_text())['status'] == 'committed'
        assert json.loads(oldest.read_text())['recovered']
    command = [sys.executable, str(ROOT / 'scripts/repl.py'), '--lfe', '--json',
               '--store', str(base / 'cli')]
    result = subprocess.run(command, input='(defun double (x) (* x 2))\n/functions\n/describe double 1\n/operations\n/quit\n',
                            text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    outputs = [json.loads(line) for line in result.stdout.splitlines()]
    assert outputs[2]['functions'][0]['name'] == 'double'
    assert outputs[3]['found'] and outputs[3]['function']['arity'] == 1
    assert outputs[4]['operations'][0]['status'] == 'committed'


def compatibility_and_limits(base):
    store = base / 'old-snapshot'
    with session(store) as bridge:
        success(bridge, '(defun old-double (x) (* x 2))')
    # Publish the original format through the actual store module. Neither
    # catalogue metadata nor operation IDs existed in those snapshots.
    command = ['erl', '+S', '2:2', '-noshell', '-pa', str(ROOT / '_build/ebin'),
               str(ROOT / '_build/deps/lfe/ebin'), '-eval',
               '[Dir]=init:get_plain_arguments(), Old=jiti_store:open(Dir), '
               'Candidate=maps:without([catalogue,\'operation-id\'], Old), '
               'jiti_store:publish(Dir,Old,Candidate), halt().', '-extra', str(store)]
    result = subprocess.run(command, text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    with session(store) as bridge:
        assert bridge.revision == 2
        described = bridge.request('describe', name='old-double', arity=1)
        assert described['found'] and described['function']['documentation'] == ''
        source = described['function']['source']
        assert source.startswith('(define-function old-double')
        assert success(bridge, '(old-double 9)')['value'] == '18'
        success(bridge, source)
        assert bridge.request('describe', name='old-double', arity=1)['found']
    with session(base / 'unicode-bounds') as bridge:
        documentation = 'é' * 5000
        success(bridge, f'(defun lengthy (x) "{documentation}" x)')
        entry = bridge.request('functions')['functions'][0]
        assert entry['documentation'] == 'é' * 512
        assert entry['documentation_truncated'] and not entry['arguments_truncated']
        entry = bridge.request('describe', name='lengthy', arity=1)['function']
        assert len(entry['source']) == 4096 and entry['source_truncated']
        # Source is stored intact; only inspection is truncated.
        assert success(bridge, '(lengthy 7)')['value'] == '7'


def main():
    with tempfile.TemporaryDirectory(prefix='jiti-lfe-diagnostics-') as directory:
        base = Path(directory)
        catalogue(base)
        diagnostics(base)
        fault_boundaries(base)
        bounds_and_cli(base)
        compatibility_and_limits(base)
    print('LFE catalogue, durable operations, real crash/publication faults, bounds, and CLI passed')


if __name__ == '__main__':
    main()
