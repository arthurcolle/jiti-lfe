#!/usr/bin/env python3
"""Actual BEAM execution through the model-facing declarative plan tools."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from lfe_repl import Bridge, Chat, FrontendError, Session, parser
from lfe_plan_tools import PLAN_TOOLS


def node(name, parent='', deps=(), check="'true", source='', kind='task', priority=0):
    return dict(id=name, parent=parent, title=name, kind=kind, dependencies=list(deps),
                priority=priority, check=check, source=source, timeout_ms=1000)


def tool(chat, op, **arguments):
    return chat._tool({'name': 'lfe_' + op, 'arguments': json.dumps(arguments)})


def cognition(bridge):
    chat = Chat.__new__(Chat)
    chat.bridge = bridge
    return chat


def result_check(plan, name, result):
    return (f"(=:= (maps:get 'result (map-get (map-get (map-get "
            f"(jiti_plan:inspect #B(\"{plan}\")) 'nodes) #B(\"{name}\")) 'job) #B()) "
            f"#B(\"#(ok {result})\"))")


def await_job(chat, plan, job):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        status = tool(chat, 'plan_status', id=plan)
        updated = tool(chat, 'plan_reconcile', id=plan, expected_version=status['plan_version'])
        entry = next(n for n in updated['nodes'] if n['id'] == job)
        if entry['status'] != 'running':
            return updated
        time.sleep(.01)
    raise AssertionError('Actual job did not finish within the test deadline.')


def lifecycle(base):
    store = base / 'lifecycle'
    b = Bridge(store)
    try:
        c = cognition(b)
        initial = tool(c, 'plan_list', offset=0)
        assert initial['plans'] == [] and initial['next_offset'] is None
        # Children and dependencies appear before their parents/prerequisites.
        nodes = [node('tail', 'root', ('left',), result_check('demo', 'tail', 42), '(+ 40 2)'),
                 node('left', 'root', check=result_check('demo', 'left', 5), source='(timer:sleep 500) (+ 2 3)'),
                 node('root', kind='group', check='')]
        created = tool(c, 'plan_create', id='demo', title='Actual pipeline', nodes=nodes)
        assert created['status'] == 'ok' and b.revision == 1 and created['ready'] == ['left'], created
        version = created['plan_version']
        stale = tool(c, 'plan_launch', id='demo', node='left', expected_version=version - 1)
        assert stale['status'] == 'rejected' and stale['reason'] == 'stale_plan_version'
        assert b.revision == 1 and 'token' not in stale
        premature = tool(c, 'plan_verify', id='demo', node='left', expected_version=version)
        assert premature['status'] == 'paused' and b.revision == 1, premature
        assert b.request('abort')['status'] == 'ok'
        blocked = tool(c, 'plan_control', id='demo', node='root', expected_version=version,
                       action='block', reason='Owner gate')
        assert blocked['ready'] == []
        unblocked = tool(c, 'plan_control', id='demo', node='root', expected_version=blocked['plan_version'],
                         action='unblock', reason='')
        assert unblocked['ready'] == ['left']
        launch = tool(c, 'plan_launch', id='demo', node='left', expected_version=unblocked['plan_version'])
        assert launch['status'] == 'ok'
        short_wait = tool(c, 'plan_wait', id='demo', expected_version=launch['plan_version'], wait_ms=0)
        assert short_wait['wait_timed_out'] and b.request('status')['status'] == 'ok', short_wait
        observed = tool(c, 'plan_wait', id='demo', expected_version=short_wait['plan_version'], wait_ms=1000)
        assert not observed['wait_timed_out'], observed
        assert observed['ready'] == [], 'An executed but unverified prerequisite admitted its dependent.'
        verified = tool(c, 'plan_verify', id='demo', node='left', expected_version=observed['plan_version'])
        assert verified['ready'] == ['tail']
        launch = tool(c, 'plan_launch', id='demo', node='tail', expected_version=verified['plan_version'])
        observed = await_job(c, 'demo', 'tail')
        verified = tool(c, 'plan_verify', id='demo', node='tail', expected_version=observed['plan_version'])
        assert all(n['status'] == 'done' for n in verified['nodes']), verified
        final_version = verified['plan_version']
        # Topology stays frozen; failed edits retain no state changes.
        revision = b.revision
        edit = tool(c, 'plan_add', id='demo', expected_version=final_version, node=node('late'))
        assert edit['status'] == 'paused' and b.revision == revision
        b.request('abort')
        listing = tool(c, 'plan_list', offset=0)
        assert listing['plans'][0]['id'] == 'demo'
        # Listing and inspection neither mutate nor launch anything.
        assert b.revision == revision
    finally:
        b.close()
    with contextlib.closing(Bridge(store)) as recovered:
        c = cognition(recovered)
        state = tool(c, 'plan_status', id='demo')
        assert state['plan_version'] == final_version and all(n['status'] == 'done' for n in state['nodes'])
        # Stored final local receipts survive. There are no replacement jobs.
        actual = recovered.request('execute', source='(=:= (jiti_processes:all) ())')
        assert actual['value'] == 'true'


def rejections(base):
    with contextlib.closing(Bridge(base / 'reject')) as b:
        c = cognition(b)
        # A combined wait cycle is rejected by the existing kernel; plan creation
        # and all intermediate additions roll back as one managed action.
        bad = [node('a', deps=('b',)), node('b', deps=('a',))]
        rejected = tool(c, 'plan_create', id='cycle', title='Cycle', nodes=bad)
        assert rejected['status'] == 'paused' and b.revision == 0, rejected
        b.request('abort')
        assert tool(c, 'plan_list', offset=0)['plans'] == []
        # Schema and graph-shape failures never reach execution.
        for nodes in ([node('a', deps=('absent',))], [node('a'), node('a')],
                      [node('a', parent='b'), node('b', parent='a')],
                      [node('a', check='')], [node('a', kind='group', source='(+ 2 3)')]):
            try:
                tool(c, 'plan_create', id='invalid', title='Invalid', nodes=nodes)
            except FrontendError:
                pass
            else:
                raise AssertionError('Invalid declarative plan reached the kernel.')
            assert b.revision == 0
        malformed = node('a')
        malformed['timeout_ms'] = True
        try:
            tool(c, 'plan_create', id='invalid', title='Invalid', nodes=[malformed])
        except FrontendError:
            pass
        else:
            raise AssertionError('Boolean accepted as a numeric timeout.')
        # IDs that look like source remain literal data, never interpolated code.
        injected = 'x") (state-put \'injected 1) #B("'
        created = tool(c, 'plan_create', id=injected, title='Literal ID', nodes=[])
        assert created['status'] == 'ok' and created['plan_id'] == injected
        assert b.request('execute', source="(state-get 'injected)")['value'] == 'undefined'
        # A completed job with a false verifier cannot be marked done.
        made = tool(c, 'plan_create', id='false-check', title='Rejected output',
                    nodes=[node('bad', source='42', check="'false")])
        launch = tool(c, 'plan_launch', id='false-check', node='bad', expected_version=made['plan_version'])
        observed = await_job(c, 'false-check', 'bad')
        result = tool(c, 'plan_verify', id='false-check', node='bad', expected_version=observed['plan_version'])
        assert result['status'] == 'paused'
        b.request('abort')
        current = tool(c, 'plan_status', id='false-check')
        assert current['nodes'][0]['status'] == 'awaiting_verification'
        # Checks that mutate managed state fail even if they return true.
        made = tool(c, 'plan_create', id='mutating-check', title='Read-only checks',
                    nodes=[node('bad', check="(state-put 'forged 1) 'true")])
        result = tool(c, 'plan_verify', id='mutating-check', node='bad', expected_version=made['plan_version'])
        assert result['status'] == 'paused'
        b.request('abort')
        assert b.request('execute', source="(state-get 'forged)")['value'] == 'undefined'
        # Explicit cancellation cleans up the owned running job.
        made = tool(c, 'plan_create', id='cancel', title='Owned cleanup',
                    nodes=[node('slow', source='(timer:sleep 500) 7')])
        launch = tool(c, 'plan_launch', id='cancel', node='slow', expected_version=made['plan_version'])
        stopped = tool(c, 'plan_control', id='cancel', node='slow', expected_version=launch['plan_version'],
                       action='cancel', reason='Owner cancellation')
        assert stopped['nodes'][0]['status'] == 'cancelled'
        active = b.request('execute', source="(lists:any (lambda (j) (=:= (map-get j 'status) 'running)) (jiti_processes:all))")
        assert active['value'] == 'false'


def pagination(base):
    with contextlib.closing(Bridge(base / 'pagination')) as b:
        source = ' '.join(f'(jiti_plan:create #B("p{i:02d}") #B("plan"))' for i in range(53))
        assert b.request('execute', source=source)['status'] == 'ok'
        c = cognition(b)
        first = tool(c, 'plan_list', offset=0)
        second = tool(c, 'plan_list', offset=first['next_offset'])
        assert len(first['plans']) == 50 and len(second['plans']) == 3 and second['next_offset'] is None
        assert first['plan_count'] == 53 and b.revision == 1
        assert tool(c, 'plan_list', offset=1000)['plans'] == []
        assert b.request('plan_list', offset=-1)['status'] == 'rejected'
        output = SimpleNamespace(result=lambda r, **kwargs: None, text=lambda text: None)
        session = Session(b, output, SimpleNamespace(mode='lfe'))
        assert session.run('/plans 50')
        try:
            session.run('/plans -1')
        except FrontendError:
            pass
        else:
            raise AssertionError('Negative plan offset accepted.')


def configuration():
    assert parser().parse_args([]).max_output_tokens == 8192
    assert parser().parse_args(['--max-output-tokens', '16384']).max_output_tokens == 16384
    for value in ('0', '-1', '32769'):
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                parser().parse_args(['--max-output-tokens', value])
            except SystemExit:
                pass
            else:
                raise AssertionError('Invalid model output budget accepted.')
    assert len(PLAN_TOOLS) == 9


def main():
    configuration()
    with tempfile.TemporaryDirectory(prefix='jiti-native-plan-tools-') as directory:
        base = Path(directory)
        lifecycle(base)
        rejections(base)
        pagination(base)
    print('Native plans: atomic construction, actual jobs, independent checks, stale fences, cancellation, pagination and recovery passed')


if __name__ == '__main__':
    main()
