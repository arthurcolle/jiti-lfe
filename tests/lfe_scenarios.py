#!/usr/bin/env python3
"""Exercise the real BEAM boundary, plus a replayable state-machine property."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from lfe_repl import Bridge, FrontendError


@contextmanager
def session(path, **options):
    bridge = Bridge(path, **options)
    try:
        assert bridge.open_result['status'] == 'ok', bridge.open_result
        yield bridge
    finally:
        bridge.close()


def successful(bridge, source, value=None, op='execute'):
    result = bridge.request(op, source=source)
    assert result['status'] == 'ok', result
    if value is not None:
        assert result['value'] == value, result
    return result


def scenarios(base):
    store = base / 'composition'
    with session(store) as bridge:
        assert successful(bridge, '(+ 2 3)', '5')['revision'] == 0
        first = successful(bridge, '(defun twice (x) (* x 2)) (state-put \'x (twice 7))', '14')
        assert first['revision'] == 1
        assert successful(bridge, '(twice (twice 3))', '12')['revision'] == 1
        assert successful(bridge, '(defun twice (x) (* x 2))')['revision'] == 1
        successful(bridge, '(state-put \'x 99) (defun twice (x) (* x 3))', 'twice', 'preview')
        successful(bridge, '(twice (state-get \'x))', '28')
        successful(bridge, '(let ((x 42)) (twice 3))', '6')
        successful(bridge, '(defun factorial ((0) 1) ((n) (* n (factorial (- n 1)))))')
        successful(bridge, '(factorial 5)', '120')
        invalid = bridge.request('develop', source='(defun bad (x) (+ not-bound 2))')
        assert invalid['status'] == 'paused'
        bridge.request('abort')
        assert not bridge.request('describe', name='bad', arity=1)['found']
        successful(bridge, '(defun forward (x) (later x))')
        assert bridge.request('execute', source='(forward 4)')['status'] == 'paused'
        successful(bridge, '(defun later (x) (+ x 1))', op='repair')
        assert bridge.request('retry')['value'] == '5'
        successful(bridge, '(io:format "discarded-output~n") (+ 1 1)', '2')
        successful(bridge, '(state-put \'x 20)')
        current = bridge.revision
        paused = bridge.request('execute', source='(state-put \'x 99) (missing 4)')
        assert paused['status'] == 'paused' and paused['revision'] == current
        token = paused['token']
        assert bridge.request('execute', source='(+ 1 1)')['status'] == 'rejected'
        assert bridge.request('repair', token=token + 1, source='(defun missing (x) x)')['status'] == 'rejected'
        successful(bridge, '(defun missing (x) (+ x 1))', 'missing', 'repair')
        assert bridge.revision == current
        retried = bridge.request('retry')
        assert retried['status'] == 'ok' and retried['value'] == '5'
        assert retried['revision'] == current + 1
        assert bridge.request('abort', token=token)['status'] == 'rejected'
        successful(bridge, '(state-get \'x)', '99')
        paused = bridge.request('execute', source='(state-put \'x 1000) (error \'failed)')
        successful(bridge, '(state-put \'x 600)', op='repair')
        assert bridge.request('abort')['status'] == 'ok'
        successful(bridge, '(state-get \'x)', '99')
        paused = bridge.request('preview', source='(future 2)')
        successful(bridge, '(defun future (x) (* x 3))', op='repair')
        retried = bridge.request('retry')
        assert retried['status'] == 'ok' and retried['value'] == '6' and 'token' not in retried
        assert not bridge.request('describe', name='future', arity=1)['found']
        # A failed repair discards all its provisional code/data.
        bridge.request('execute', source='(future 2)')
        failed = bridge.request('repair', source='(state-put \'x 800) (error \'failed)')
        assert failed['status'] == 'rejected' and 'token' not in failed
        successful(bridge, '(state-get \'x)', '99')
        for invalid in ('(+ 1', 'not-a-bound-variable', ''):
            assert bridge.request('execute', source=invalid)['status'] == 'paused'
            bridge.request('abort')
        assert bridge.request('execute', source='(state-put \'pid (self))')['status'] == 'paused'
        bridge.request('abort')
        try:
            competing = Bridge(store)
        except FrontendError as error:
            assert 'active writer' in str(error)
        else:
            competing.close()
            raise AssertionError('two writers opened one store')
        # Kill a real VM with a pending operation; recovery must use CURRENT.
        paused = bridge.request('execute', source='(state-put \'x 1234) (error \'unfinished)')
        abandoned_token = paused['token']
        bridge.process.kill()
        bridge.broken = True
    with session(store) as recovered:
        successful(recovered, '(twice (state-get \'x))', '198')
        assert 'token' not in recovered.request('status')
        assert recovered.request('retry', token=abandoned_token)['status'] == 'rejected'
        current = recovered.revision
        rolled = recovered.request('rollback', revision=1)
        assert rolled['status'] == 'ok' and rolled['revision'] == current + 1
        successful(recovered, '(twice (state-get \'x))', '28')
        assert str(current) in recovered.request('history')['value']
        successful(recovered, '(forget \'twice 1)', 'ok')
        assert not recovered.request('describe', name='twice', arity=1)['found']
    with session(base / 'checks', safety=["(orelse (=:= (state-get 'x) 'undefined) (>= (state-get 'x) 0))"],
                 goals=["(=:= (state-get 'x) 7)"]) as bridge:
        assert not successful(bridge, "(state-put 'x 3)")['goal']
        current = bridge.revision
        assert bridge.request('execute', source="(state-put 'x -1)")['status'] == 'rejected'
        assert bridge.revision == current
        successful(bridge, "(state-get 'x)", '3')
        assert successful(bridge, "(state-put 'x 7)")['goal']
        assert bridge.request('rollback', revision=0)['status'] == 'ok'
    unsafe = Bridge(base / 'checks', safety=['(error \'bad_check)'])
    try:
        assert unsafe.open_result['status'] == 'error'
    finally:
        unsafe.close()
    mutating = Bridge(base / 'mutating-check', safety=["(state-put 'x 9) 'true"])
    try:
        assert mutating.open_result['status'] == 'error'
    finally:
        mutating.close()
    with session(base / 'deadline', timeout_ms=50) as bridge:
        result = bridge.request('execute', source="(receive (after 5000 'late))")
        assert result['status'] == 'paused' and 'timeout' in result['reason']
        bridge.request('abort')
        successful(bridge, '(+ 4 5)', '9')
    with session(base / 'orphan') as bridge:
        successful(bridge, "(state-put 'x 1)")
        (base / 'orphan' / '2.term').write_bytes(b'orphaned publication')
        assert successful(bridge, "(state-put 'x 2)")['revision'] == 3
        assert bridge.request('rollback', revision=2)['status'] == 'rejected'
    corrupt = base / 'corrupt'
    with session(corrupt) as bridge:
        successful(bridge, "(state-put 'x 1)")
    (corrupt / '1.term').write_bytes(b'corrupt snapshot')
    broken = Bridge(corrupt)
    try:
        assert broken.open_result['status'] == 'error'
    finally:
        broken.close()
    for path in store.glob('*.term'):
        assert path.stat().st_mode & 0o777 == 0o600
    piped = subprocess.run([sys.executable, str(ROOT / 'scripts/repl.py'), '--lfe', '--json',
                            '--store', str(base / 'pipe')], input='(defun double (x)\n (* x 2))\n(double 5)\n/quit\n',
                           text=True, capture_output=True, timeout=15)
    assert piped.returncode == 0, piped.stderr
    assert json.loads(piped.stdout.splitlines()[-2])['value'] == '10'


def check_trace(trace):
    """Reference model: only accepted final managed changes create revisions."""
    state, revision = {}, 0
    with tempfile.TemporaryDirectory(prefix='jiti-lfe-property-') as directory:
        with session(directory) as bridge:
            for index, action in enumerate(trace):
                kind, key, value = action
                candidate = dict(state)
                if kind in ('put', 'preview', 'fail'):
                    source = f"(state-put '{key} {value})"
                    candidate[key] = value
                else:
                    source = f"(state-delete '{key})"
                    candidate.pop(key, None)
                if kind == 'fail':
                    source += " (error 'generated_failure)"
                result = bridge.request('preview' if kind == 'preview' else 'execute', source=source)
                expected = 'paused' if kind == 'fail' else 'ok'
                assert result['status'] == expected, (index, action, result)
                if kind == 'fail':
                    bridge.request('abort')
                elif kind != 'preview':
                    if candidate != state:
                        revision += 1
                    state = candidate
                assert bridge.revision == revision, (index, action, result)
                for name in ('a', 'b'):
                    observed = bridge.request('execute', source=f"(state-get '{name})")
                    assert observed['value'] == str(state.get(name, 'undefined')), (index, action, observed)
                    assert observed['revision'] == revision


def minimize(trace):
    width = max(1, len(trace) // 2)
    while width:
        offset = 0
        while offset < len(trace):
            candidate = trace[:offset] + trace[offset + width:]
            try:
                check_trace(candidate)
            except (AssertionError, FrontendError):
                trace = candidate
            else:
                offset += width
        width //= 2
    return trace


def property_check(seed):
    randomizer = random.Random(seed)
    trace = [[randomizer.choice(('put', 'delete', 'preview', 'fail')),
              randomizer.choice(('a', 'b')), randomizer.randrange(-3, 4)] for _ in range(60)]
    try:
        check_trace(trace)
    except (AssertionError, FrontendError):
        minimized = minimize(trace)
        directory = ROOT / '.image-agent/lfe-failures'
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        artifact = directory / f'{seed}.json'
        fd = os.open(artifact, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump({'seed': seed, 'trace': minimized}, stream)
        print(f'Replay: python3 tests/lfe_scenarios.py --replay {artifact}', file=sys.stderr)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--replay', type=Path)
    options = parser.parse_args()
    if options.replay:
        check_trace(json.loads(options.replay.read_text())['trace'])
        print('LFE property trace passed')
        return
    with tempfile.TemporaryDirectory(prefix='jiti-lfe-scenarios-') as directory:
        scenarios(Path(directory))
    for seed in (424242, 8128, 20261005):
        property_check(seed)
    print('LFE scenarios and 180 generated state-machine actions passed')


if __name__ == '__main__':
    main()
