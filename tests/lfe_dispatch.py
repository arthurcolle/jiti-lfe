"""Actual native dispatch: ambiguity, hot replacement, rollback and recovery."""
from pathlib import Path
import sys
import tempfile
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from lfe_repl import Bridge

ROOT = Path(__file__).resolve().parents[1]

def ok(bridge, source, expected=None, op='execute'):
    result = bridge.request(op, source=source)
    assert result['status'] == 'ok', result
    if expected is not None:
        assert result['value'] == expected, result
    return result

with tempfile.TemporaryDirectory(prefix='jiti-dispatch-') as temporary:
    bridge = Bridge(temporary, timeout_ms=5000)
    try:
        ok(bridge, (ROOT/'examples/dynamic-dispatch.lfe').read_text(), '925')
        ok(bridge, "(invoke (lambda (x) (* x 3)) '(7))", '21')
        ok(bridge, "(invoke (tuple 'remote 'lists 'sum) (list '(1 2 3)))", '6')
        ok(bridge, "(=:= (state-get 'absolute-values) '(3 4 5))", 'true')
        numeric = ok(bridge, "(map-call 'price-int '(2 3 4))")
        assert numeric['json_available'] and numeric['value_json'] == '[200,300,400]', numeric
        ok(bridge, "(map-call (partial (lambda (a b) (+ a b)) '(10)) '(1 2 3))", '(11 12 13)')
        ok(bridge, "(defun price-int (value) (* value 200))")
        ok(bridge, "(invoke (state-get 'pricing-pipeline) '(3))", '625')
        revision = bridge.revision
        ok(bridge, "(method-delete 'price '(integer)) (dispatch 'price '(3))", '300', op='preview')
        assert bridge.revision == revision
        ok(bridge, "(dispatch 'price '(3))", '600')
        # Overlaps on different arguments are incomparable, not a lucky winner.
        ok(bridge, "(defun left (a b) 'left) (defun right (a b) 'right) "
           "(method-put 'pair '(integer any) 'left) (method-put 'pair '(any integer) 'right)")
        failed = bridge.request('execute', source="(state-put 'should-not-commit 1) (dispatch 'pair '(1 2))")
        assert failed['status'] == 'paused' and 'ambiguous_dispatch' in failed['reason'], failed
        bridge.request('abort')
        ok(bridge, "(state-get 'should-not-commit)", 'undefined')
        ok(bridge, "(method-put 'pair '(integer integer) 'left) (dispatch 'pair '(1 2))", 'left')
        ok(bridge, "(defun tagged (x) (element 2 x)) (method-put 'read (list (tuple 'tag 'record)) 'tagged) "
           "(dispatch 'read (list (tuple 'record 42)))", '42')
        # Failed edits discard method registrations along with other managed data.
        failed = bridge.request('execute', source="(method-delete 'price '(integer)) (error 'discard)")
        assert failed['status'] == 'paused'
        bridge.request('abort')
        ok(bridge, "(dispatch 'price '(3))", '600')
        # Rollback restores definitions and descriptors together, then resolves live.
        old = bridge.revision
        ok(bridge, "(defun price-int (value) (* value 300))")
        assert bridge.request('rollback', revision=old)['status'] == 'ok'
        ok(bridge, "(invoke (state-get 'pricing-pipeline) '(3))", '625')
    finally:
        bridge.close()
    recovered = Bridge(temporary, timeout_ms=5000)
    try:
        ok(recovered, "(invoke (state-get 'pricing-pipeline) '(3))", '625')
        ok(recovered, "(dispatch 'pair '(1 2))", 'left')
        assert recovered.request('execute', source="(state-put 'closure (lambda (x) x))")['status'] == 'paused'
        recovered.request('abort')
        ok(recovered, "(state-get 'closure)", 'undefined')
        # Convenience names do not seize names already owned by managed code.
        ok(recovered, "(defun compose (x) (tuple 'owned x)) (compose 7)", '#(owned 7)')
        ok(recovered, "(jiti_dispatch:invoke (jiti_dispatch:compose '(price-int)) '(3))", '600')
    finally:
        recovered.close()
print('PASS native polymorphic execution: live resolution, closures, composition, ambiguity, preview, rollback, recovery')
