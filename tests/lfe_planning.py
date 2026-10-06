#!/usr/bin/env python3
"""Planner invariants and actual asynchronous/local/distributed process lifetimes."""
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from lfe_repl import Bridge


@contextmanager
def session(directory):
    bridge = Bridge(directory, timeout_ms=12000)
    try:
        assert bridge.open_result['status'] == 'ok', bridge.open_result
        yield bridge
    finally:
        bridge.close()


def execute(b, source, expected=None):
    r = b.request('execute', source=source)
    assert r['status'] == 'ok', r
    if expected is not None:
        assert r['value'] == expected, r
    return r


def rejected(b, source):
    revision = b.revision
    r = b.request('execute', source=source)
    assert r['status'] == 'paused', r
    assert b.request('abort')['status'] == 'ok'
    assert b.revision == revision, (revision, b.revision)


def version(plan='demo'):
    return f'(map-get (jiti_plan:inspect #B("{plan}")) \'version)'


def plan_tests(base):
    with session(base / 'plans') as b:
        listing = b.request('workspace_list', path='', offset=0)
        assert listing['status'] == 'ok' and len(listing['entries']) <= 80
        reading = b.request('workspace_read', path='dsco-cli/src/main.c', offset=0)
        assert reading['status'] == 'ok' and reading['bytes'] == 12000 and reading['next_offset'] == 12000
        for path in ('../README.md','/etc/passwd','agents.erl/.runtime/file.md','dsco-cli/.env'):
            assert b.request('workspace_read', path=path, offset=0)['status'] == 'rejected'
        assert b.request('workspace_read', path='jiti/README.md', offset=-1)['status'] == 'rejected'
        assert b.request('status')['status'] == 'ok'
        execute(b, '(jiti_plan:create #B("demo") #B("Portfolio runtime"))')
        execute(b, '(jiti_plan:add #B("demo") #B("root") \'none #B("Root") \'group () 0 #B() \'none)')
        execute(b, '(jiti_plan:add #B("demo") #B("review") #B("root") #B("Review") \'task () 10 #B("(=:= (state-get \'reviewed) \'true)") \'none)')
        execute(b, '(jiti_plan:add #B("demo") #B("jobs") #B("root") #B("Jobs") \'group (list #B("review")) 0 #B() \'none)')
        for name in ('b', 'a'):
            execute(b, f'(jiti_plan:add #B("demo") #B("{name}") #B("jobs") #B("{name}") \'task () 5 #B("\'true") (map \'adapter \'lfe \'source #B("(timer:sleep 100) (+ 2 3)")))')
        execute(b, '(=:= (map-get (jiti_plan:ready #B("demo")) \'ready) (list #B("review")))', 'true')
        # Independent dependency cycles and ancestor admission deadlocks reject.
        rejected(b, '(jiti_plan:depend #B("demo") #B("review") #B("jobs"))')
        rejected(b, '(jiti_plan:depend #B("demo") #B("a") #B("unknown"))')
        rejected(b, f'(jiti_plan:verify #B("demo") #B("review") {version()})')
        execute(b, '(state-put \'reviewed \'true)')
        execute(b, f'(jiti_plan:verify #B("demo") #B("review") {version()})')
        execute(b, '(=:= (map-get (jiti_plan:ready #B("demo")) \'ready) (list #B("a") #B("b")))', 'true')
        rejected(b, '(jiti_plan:depend #B("demo") #B("b") #B("a"))')
        execute(b, '(jiti_plan:block #B("demo") #B("jobs") #B("Operator gate"))')
        execute(b, '(=:= (map-get (jiti_plan:ready #B("demo")) \'ready) ())', 'true')
        execute(b, '(jiti_plan:unblock #B("demo") #B("jobs"))')
        old = execute(b, version())['value']
        execute(b, f'(jiti_plan:launch #B("demo") #B("a") {old})')
        rejected(b, f'(jiti_plan:launch #B("demo") #B("b") {old})')
        execute(b, '(length (jiti_processes:all))', '1')
        execute(b, f'(jiti_plan:launch #B("demo") #B("b") {version()})')
        time.sleep(.15)
        execute(b, '(jiti_plan:reconcile #B("demo"))')
        for name in ('a', 'b'):
            execute(b, f'(jiti_plan:verify #B("demo") #B("{name}") {version()})')
        execute(b, '(=:= (map-get (map-get (map-get (jiti_plan:inspect #B("demo")) \'nodes) #B("root")) \'status) \'done)', 'true')
        execute(b, '(lists:all (lambda (j) (=:= (map-get j \'result) #B("#(ok 5)"))) (jiti_processes:all))', 'true')
        # Invalid handles do not crash the process manager.
        rejected(b, '(jiti_processes:inspect 42)')
        execute(b, '(is_pid (whereis \'jiti_processes))', 'true')
        execute(b, '(jiti_processes:configure #B("other-owner"))', '#(error owner_is_immutable)')
        execute(b, '(state-put \'long-job (element 2 (jiti_processes:start (map \'adapter \'lfe \'source #B("(receive (after 10000 true))") \'timeout_ms 20000))))')
        execute(b, '(map-get (jiti_processes:stop-handle (state-get \'long-job)) \'status)', 'stopped')
        execute(b, '(state-put \'orphan (element 2 (jiti_processes:start (map \'adapter \'lfe \'source #B("(receive (after 10000 true))") \'timeout_ms 20000))))')
        # A real manager failure kills its owned worker and loses runtime leases.
        execute(b, '(let* ((jobs (map-get (sys:get_state \'jiti_processes) \'jobs)) (pid (map-get (map-get jobs (map-get (state-get \'orphan) \'id)) \'pid))) (exit (whereis \'jiti_processes) \'kill) (timer:sleep 50) (not (erlang:is_process_alive pid)))', 'true')
        execute(b, '(map-get (jiti_processes:inspect (state-get \'orphan)) \'status)', 'unknown')
        execute(b, '(length (jiti_processes:all))', '0')
    cli = subprocess.run([sys.executable, str(ROOT/'scripts/repl.py'), '--lfe', '--store', str(base/'plans'), '--plain'],
                         input='/plan demo\n/quit\n', text=True, capture_output=True, timeout=15)
    assert cli.returncode == 0 and 'plan: demo' in cli.stdout and 'root group done' in cli.stdout, cli.stdout + cli.stderr
    with session(base / 'plans') as b:
        execute(b, '(=:= (map-get (map-get (map-get (jiti_plan:inspect #B("demo")) \'nodes) #B("root")) \'status) \'done)', 'true')
        execute(b, '(map-get (jiti_processes:inspect (state-get \'orphan)) \'status)', 'unknown')
    with session(base / 'failure') as b:
        execute(b, '(jiti_plan:create #B("failure") #B("Failure proof"))')
        execute(b, '(jiti_plan:add #B("failure") #B("root") \'none #B("Root") \'group () 0 #B() \'none)')
        execute(b, '(jiti_plan:add #B("failure") #B("job") #B("root") #B("Timeout") \'task () 0 #B("\'true") (map \'adapter \'lfe \'source #B("(receive (after 10000 true))") \'timeout_ms 30))')
        execute(b, f'(jiti_plan:launch #B("failure") #B("job") {version("failure")})')
        time.sleep(.06)
        execute(b, '(jiti_plan:reconcile #B("failure"))')
        execute(b, '(map-get (map-get (map-get (jiti_plan:inspect #B("failure")) \'nodes) #B("root")) \'status)', 'failed')
        rejected(b, f'(jiti_plan:verify #B("failure") #B("job") {version("failure")})')


def distributed(base):
    agents = ROOT.parent / 'agents.erl'
    sys.path.insert(0, str(agents / 'scripts'))
    from test_persistent_agents import compile_runtime
    ebin = base / 'actor-ebin'
    ebin.mkdir()
    compile_runtime(ebin)
    directory = base / 'durable-actors'
    node = f'agents_jiti_test_{os.getpid()}@127.0.0.1'
    env = os.environ.copy()
    env['ERL_EPMD_ADDRESS'] = '127.0.0.1'
    source = ('[Dir]=init:get_plain_arguments(), application:ensure_all_started(crypto), '
              '{ok,_}=agent_registry:start_link(#{}), {ok,_}=agent_supervisor:start_link(), '
              '{ok,_}=persistent_agent_service:start_link(Dir), io:format("READY~n"), receive stop -> ok end.')
    def start():
        p = subprocess.Popen(['erl','+S','2:2','-noshell','-name',node,'-kernel','inet_dist_use_interface',
                              '{127,0,0,1}','-pa',str(ebin),'-eval',source,'-extra',str(directory)],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env)
        assert p.stdout.readline().strip() == 'READY'
        return p
    process = start()
    store = base / 'distributed-plan'
    try:
        with session(store) as b:
            execute(b, f'(state-put \'actor (element 2 (jiti_processes:start (map \'adapter \'agent \'node \'{node} \'logical_id #B("durable-demo")))))')
            execute(b, '(map-get (jiti_processes:inspect (state-get \'actor)) \'status)', 'running')
            execute(b, '(state-put \'old-generation (map-get (state-get \'actor) \'generation))')
        process.terminate()
        process.wait(timeout=5)
        process = start()
        with session(store) as b:
            execute(b, '(map-get (jiti_processes:inspect (state-get \'actor)) \'status)', 'stale')
            execute(b, '(map-get (jiti_processes:stop-handle (state-get \'actor)) \'status)', 'stale')
            execute(b, '(state-put \'actor (jiti_processes:reconcile (state-get \'actor)))')
            execute(b, '(> (map-get (state-get \'actor) \'generation) (state-get \'old-generation))', 'true')
            execute(b, '(map-get (jiti_processes:inspect (state-get \'actor)) \'status)', 'running')
            execute(b, '(map-get (jiti_processes:stop-handle (map-set (state-get \'actor) \'owner #B("wrong"))) \'status)', 'unknown')
            execute(b, '(map-get (jiti_processes:inspect (state-get \'actor)) \'status)', 'running')
            execute(b, '(state-put \'actor (jiti_processes:stop-handle (state-get \'actor)))')
            execute(b, '(map-get (state-get \'actor) \'status)', 'stopped')
    finally:
        process.terminate()
        process.wait(timeout=5)


def main():
    with tempfile.TemporaryDirectory(prefix='jiti-planning-') as tmp:
        base = Path(tmp)
        plan_tests(base)
        distributed(base)
    print('Hierarchical planning, real concurrent jobs, manager/VM recovery, durable remote actors and fencing passed')


if __name__ == '__main__':
    main()
