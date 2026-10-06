#!/usr/bin/env python3
"""Real scheduler rollouts and the child tool boundary, without inference."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from farm_rollouts import CandidateChat, FrontendError, SessionBridge, fixture, run_rollout, validate, persist, execute


def main():
    for value in ({'grouping':'flat','priority':'id','width':True},
                  {'grouping':'flat','priority':'id','width':3},
                  {'grouping':'flat','priority':'id','width':1,'source':'(os:cmd ...)'}):
        try:
            validate(value)
        except FrontendError:
            pass
        else:
            raise AssertionError('Invalid or executable candidate was admitted')
    # Exercise dispatch itself; merely hiding a tool from the model is insufficient.
    child = object.__new__(CandidateChat)
    child.grants = ('contract',)
    for name in ('probe', 'execute', 'grant', 'workspace_read'):
        try:
            child._tool({'name':name, 'arguments':'{}'})
        except FrontendError:
            pass
        else:
            raise AssertionError('Out-of-grant child tool was dispatched')
    with tempfile.TemporaryDirectory(prefix='jiti-empirical-') as tmp:
        with SessionBridge(Path(tmp)/'receipt') as bridge:
            persist(bridge, 'timing', {'elapsed_ms': 42.125, 'accepted': True})
            assert bridge.request('plan_status', id='')['status'] == 'rejected'
            assert bridge.request('status')['status'] == 'ok'
        with SessionBridge(Path(tmp)/'receipt') as bridge:
            assert execute(bridge, '(=:= (map-get (state-get #B("timing")) #B("elapsed_ms")) 42.125)')['value'] == 'true'
        for grouping in ('flat','levels','components'):
            result = run_rollout(Path(tmp)/grouping,
                                 dict(grouping=grouping,priority='critical_path',width=2), fixture(198))
            assert result['accepted'] and result['tasks'] == 6
            assert result['peak_jobs'] <= 2
            assert sum(t['event']=='verified' for t in result['trace']) == 6
    print('Empirical rollouts: actual jobs in three decompositions, independent checks, exact precedence, resource cap and denied tool dispatch passed')


if __name__ == '__main__':
    main()
