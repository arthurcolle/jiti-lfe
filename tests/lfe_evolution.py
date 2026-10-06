#!/usr/bin/env python3
"""Offline real-Bridge tests; compile into a disposable tree, not the shared build.

Run: python3 tests/lfe_evolution.py
Requires the existing pinned LFE dependency and Erlang; no inference or network.
"""
from contextlib import contextmanager
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import lfe_repl

COUNT = 0


def execute(b, source, expected=None, op='execute'):
    global COUNT
    r = b.request(op, source=source)
    assert r['status'] == 'ok', (source, r)
    if expected is not None:
        assert r['value'] == expected, (source, r)
    COUNT += 1
    return r


@contextmanager
def session(path, **kw):
    b = lfe_repl.Bridge(path, timeout_ms=3000, **kw)
    try:
        assert b.open_result['status'] == 'ok', b.open_result
        yield b
    finally:
        b.close()


def proposal(id='p', candidates="'((lambda (x) (+ x 1)))", train="'(((0) 1) ((2) 3))",
             heldout="'(((7) 8) ((-3) -2))", safety="'(((0) -10 10) ((9) -20 20))",
             timeout=200, population=4, generations=1, seed=1, name='f'):
    return (f'(jiti_evolution:propose #B("{id}") \'{name} 1 {candidates} {train} {heldout} {safety} '
            f'(map \'seed {seed} \'population {population} \'generations {generations} \'timeout_ms {timeout}))')


def status(source):
    return f"(map-get {source} 'status)"


def reason(source):
    return f"(map-get {source} 'reason)"


def tests(base):
    store = base / 'success'
    with session(store) as b:
        initial = execute(b, "(defun f (x) x) (defun untouched (x) (* x 2)) (state-put 'keep 42)")['revision']
        execute(b, "(=:= (jiti_evolution:generate 'f 1 1 4 2) (jiti_evolution:generate 'f 1 1 4 2))", 'true')
        execute(b, "(jiti_evolution:generate 'f 1 1 1 1)", '((lambda (x) (+ x 1)))')
        execute(b, status(proposal(candidates="'generate", population=1)), 'ready')
        receipt_revision = b.revision
        execute(b, "(let ((r (jiti_evolution:inspect #B(\"p\")))) (andalso (=:= (map-get (map-get r 'baseline) 'train) 2) (=:= (map-get (map-get r 'winner) 'train) 0) (=:= (map-get (map-get r 'winner) 'heldout) 0) (=:= (byte_size (map-get r 'base_hash)) 64) (=:= (byte_size (map-get r 'snapshot_hash)) 64) (=:= (byte_size (map-get r 'digest)) 64) (=:= (byte_size (map-get (map-get r 'winner) 'hash)) 64)))", 'true')
        execute(b, '(f 7)', '7')
        # Inspect is read-only: it must not consume the one-publication fence.
        assert b.revision == receipt_revision
    # A durable receipt is reusable across a real VM restart.
    with session(store) as b:
        execute(b, "(let* ((before (get 'jiti_candidate)) (r (jiti_evolution:promote #B(\"p\"))) (after (get 'jiti_candidate))) (andalso (=:= (map-get r 'status) 'promoted) (=:= (maps:remove 'definitions before) (maps:remove 'definitions after)) (=:= (maps:remove #(f 1) (map-get before 'definitions)) (maps:remove #(f 1) (map-get after 'definitions)))))", 'true')
        execute(b, '(f 7)', '8')
        execute(b, '(untouched 7)', '14')
        execute(b, "(state-get 'keep)", '42')
        execute(b, reason('(jiti_evolution:promote #B("p"))'), 'stale_baseline')
    with session(store) as b:
        execute(b, '(f 7)', '8')
        result = b.request('rollback', revision=initial)
        assert result['status'] == 'ok', result
        execute(b, '(f 7)', '7')
        execute(b, '(jiti_evolution:inspect #B("p"))', 'undefined')
    with session(store) as b:
        execute(b, '(f 7)', '7')
        execute(b, "(state-get 'keep)", '42')

    cases = [
        ('heldout', dict(heldout="'(((7) 7) ((-3) -3))"), 'heldout_failed'),
        ('tie', dict(candidates="'((lambda (x) (+ x 1)) (lambda (x) (+ 1 x)))"), 'tie'),
        ('no-improvement', dict(candidates="'((lambda (x) x))"), 'no_improvement'),
        ('safety', dict(safety="'(((0) 0 0))"), 'safety_failed'),
        ('unsafe-base', dict(safety="'(((0) 1 2))"), 'baseline_unsafe'),
        ('timeout', dict(timeout=0), 'timeout'),
        ('empty-safety', dict(safety="'()"), 'invalid_proposal'),
        ('empty-train', dict(train="'()"), 'invalid_proposal'),
        ('empty-heldout', dict(heldout="'()"), 'invalid_proposal'),
        ('overlap', dict(heldout="'(((0) 1))"), 'invalid_proposal'),
        ('duplicate-input', dict(train="'(((0) 1) ((0) 2))"), 'invalid_proposal'),
        ('duplicate-candidate', dict(candidates="'((lambda (x) x) (lambda (x) x))"), 'invalid_proposal'),
        ('effect', dict(candidates="'((lambda (x) (state-put 'pwned 1)))"), 'invalid_proposal'),
        ('remote', dict(candidates="'((lambda (x) (timer:sleep 1000)))"), 'invalid_proposal'),
        ('deep', dict(candidates="'((lambda (x) " + '(+ 1 ' * 9 + 'x' + ')' * 9 + '))'), 'invalid_proposal'),
        ('wide', dict(population=33), 'invalid_proposal'),
        ('generations', dict(generations=9), 'invalid_proposal'),
        ('total-budget', dict(population=32, generations=3), 'invalid_proposal'),
        ('arity', dict(candidates="'((lambda (x y) (+ x y)))"), 'invalid_proposal'),
        ('seed', dict(seed=-1), 'invalid_proposal'),
        ('missing', dict(name='absent'), 'invalid_proposal'),
        ('overflow', dict(candidates="'((lambda (x) (* 1000000 1000000)))"), 'invalid_proposal'),
    ]
    with session(base / 'rejections') as b:
        execute(b, '(defun f (x) x)')
        for id, kwargs, why in cases:
            execute(b, reason(proposal(id=id, **kwargs)), why)
            execute(b, '(f 7)', '7')
        execute(b, "(state-get 'pwned)", 'undefined')
        execute(b, reason('(jiti_evolution:promote #B("heldout"))'), 'stale_baseline')

    # Rejected-but-fresh receipts cannot promote either.
    with session(base / 'not-ready') as b:
        execute(b, '(defun f (x) x)')
        execute(b, reason(proposal(heldout="'(((7) 7))")), 'heldout_failed')
        execute(b, reason('(jiti_evolution:promote #B("p"))'), 'proposal_not_ready')

    for change in ("(state-put 'drift 1)", '(defun f (x) (+ x 2))', '(defun other (x) x)'):
        with session(base / ('stale-' + str(len(list(base.iterdir()))))) as b:
            execute(b, '(defun f (x) x)')
            execute(b, status(proposal()), 'ready')
            execute(b, change)
            execute(b, reason('(jiti_evolution:promote #B("p"))'), 'stale_baseline')

    with session(base / 'same-action') as b:
        execute(b, '(defun f (x) x)')
        execute(b, proposal() + ' ' + reason('(jiti_evolution:promote #B("p"))'), 'stale_baseline')

    with session(base / 'tamper') as b:
        execute(b, '(defun f (x) x)')
        execute(b, status(proposal()), 'ready')
        execute(b, "(state-put #(jiti_evolution #B(\"p\")) (map-set (jiti_evolution:inspect #B(\"p\")) 'winner (map 'ast '(lambda (x) 99))))")
        execute(b, reason('(jiti_evolution:promote #B("p"))'), 'invalid_proposal')

    # The outer controller safety contract still decides publication.
    check = "(orelse (=:= (state-get 'armed) 'undefined) (=:= (f 0) 0))"
    with session(base / 'controller', safety=[check]) as b:
        execute(b, "(defun f (x) x) (state-put 'armed 'true)")
        execute(b, status(proposal()), 'ready')
        revision = b.revision
        result = b.request('execute', source='(jiti_evolution:promote #B("p"))')
        assert result['status'] == 'rejected', result
        assert b.revision == revision
        execute(b, '(f 0)', '0')

    # Exercise recomputation, not just receipt hashing: a trusted local fixture
    # edit with a recomputed digest must fail even inside the same snapshot.
    with session(base / 'reverify') as b:
        execute(b, '(defun f (x) x)')
        execute(b, status(proposal()), 'ready')
        execute(b, "(let* ((s (get 'jiti_candidate)) (r (maps:remove 'digest (jiti_evolution:inspect #B(\"p\")))) (changed (map-set r 'heldout '(((7) 7)))) (h (binary:encode_hex (crypto:hash 'sha256 (term_to_binary changed '(deterministic)))))) (put 'jiti_candidate (map-set s 'state (map-set (map-get s 'state) #(jiti_evolution #B(\"p\")) (map-set changed 'digest h)))) (let ((reason (map-get (jiti_evolution:promote #B(\"p\")) 'reason))) (put 'jiti_candidate s) reason))", 'reverification_failed')
        execute(b, '(f 7)', '7')

    with session(base / 'example') as b:
        # Each top-level form is a separate publication, as in the interactive REPL.
        source = (ROOT / 'examples/evolution.lfe').read_text()
        for line in source.splitlines():
            if line and not line.startswith(';'):
                execute(b, line)
        execute(b, '(estimate 7)', '8')


def main():
    with tempfile.TemporaryDirectory(prefix='jiti-evolution-') as directory:
        base = Path(directory)
        tree = base / 'runtime'
        (tree / '_build/ebin').mkdir(parents=True)
        (tree / '_build/deps').mkdir()
        (tree / 'scripts').mkdir()
        shutil.copytree(ROOT / 'src', tree / 'src')
        shutil.copy2(ROOT / 'scripts/build-lfe.sh', tree / 'scripts/build-lfe.sh')
        lfe = ROOT / '_build/deps/lfe'
        (tree / '_build/deps/lfe').symlink_to(lfe, target_is_directory=True)
        env = os.environ.copy()
        env['PATH'] = str(lfe / 'bin') + os.pathsep + env['PATH']
        subprocess.run([str(lfe / 'bin/lfec'), '-pa', str(lfe / 'ebin'), '-o', str(tree / '_build/ebin'),
                        *map(str, sorted((tree / 'src').glob('*.lfe')))], check=True, env=env, timeout=60)
        (tree / '_build/ebin/.build-ok').touch()
        original = lfe_repl.ROOT
        lfe_repl.ROOT = tree
        try:
            tests(base)
        finally:
            lfe_repl.ROOT = original
    print(f'PASS: {COUNT} Bridge assertions; isolated LFE compilation, replay, rejection, fences, promotion, controller safety, rollback/reopen')


if __name__ == '__main__':
    main()
