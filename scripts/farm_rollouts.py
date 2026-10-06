#!/usr/bin/env python3
"""Explicit bounded empirical Jiti experiment; never a daemon or auto-promotion.

Durable identities use agents.erl; accepted plans/jobs use the real LFE kernel.
Models propose a small scheduling policy. They cannot execute source, alter the
verifier, grant tools, start actors, or inspect the held-out task set.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import html
import json
import math
import os
from pathlib import Path
import random
import time

from lfe_repl import Bridge, Chat, FrontendError, integer

ROOT = Path(__file__).resolve().parents[1]
POLICY_FIELDS = {'grouping', 'priority', 'width'}
BUNDLES = ((), ('contract',), ('probe',), ('contract', 'probe'),
           ('trace',), ('contract', 'probe', 'trace'))
BASELINE = {'grouping': 'flat', 'priority': 'id', 'width': 1}
CONTRACT = {
    'domain': 'owned asynchronous arithmetic jobs with precedence constraints',
    'grouping': ['flat', 'levels', 'components'],
    'priority': ['id', 'critical_path'], 'width': [1, 2],
    'semantics': ['Every task runs once; all original dependencies are retained.',
                  'levels adds whole-level completion barriers; components groups connected jobs.',
                  'A group does not execute cognition and is not a fixed agent role.',
                  'Only a successful runtime result plus an independent exact-result check completes work.'],
    'costs': ['Measured elapsed execution time includes local orchestration.',
              'Task delay is controlled, arithmetic output is independently verified.',
              'Group node counts and actual task counts are separate evidence.'],
    'selection': 'All outputs must pass. Rank elapsed time on common held-out tasks; retain ties and failures.',
    'limits': 'This tests a narrow scheduling policy, not general learning, revenue or MuZero training.',
}


def validate(policy):
    if (not isinstance(policy, dict) or set(policy) != POLICY_FIELDS
            or policy['grouping'] not in CONTRACT['grouping']
            or policy['priority'] not in CONTRACT['priority']
            or not integer(policy['width']) or policy['width'] not in (1, 2)):
        raise FrontendError('Candidate violates the sealed scheduling policy schema.')
    return policy


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def binary(text):
    # Use UTF-8 bytes, never shell interpolation or model-authored LFE source.
    return '#B(' + ' '.join(map(str, str(text).encode())) + ')'


def literal(value):
    if isinstance(value, str):
        return binary(value)
    if isinstance(value, bool):
        return "'true" if value else "'false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and math.isfinite(value):
        return repr(value)
    if isinstance(value, list):
        return '(list ' + ' '.join(map(literal, value)) + ')'
    if isinstance(value, dict):
        return '(map ' + ' '.join(binary(k) + ' ' + literal(v) for k, v in value.items()) + ')'
    if value is None:
        return "'undefined"
    raise TypeError('Not a durable experiment value.')


def execute(bridge, source):
    result = bridge.request('execute', source=source)
    if result['status'] != 'ok':
        raise FrontendError('Experiment kernel action did not commit: ' + result['reason'])
    return result


def fixture(seed, size=6):
    rng = random.Random(seed)
    tasks = []
    for index in range(size):
        deps = [f't{j}' for j in range(index) if rng.random() < .22]
        left, right = rng.randrange(1, 40), rng.randrange(1, 40)
        tasks.append(dict(id=f't{index}', deps=deps, left=left, right=right,
                          delay_ms=rng.choice((30, 60, 90))))
    return {'seed': seed, 'tasks': tasks}


def assignment(tasks, grouping):
    groups, parents = {}, {}
    if grouping == 'flat':
        return groups, {t['id']: 'root' for t in tasks}
    if grouping == 'levels':
        levels = {}
        for t in tasks:
            levels[t['id']] = 1 + max((levels[d] for d in t['deps']), default=-1)
        for level in sorted(set(levels.values())):
            groups[f'g{level}'] = [] if level == 0 else [f'g{level-1}']
        parents = {key: f'g{level}' for key, level in levels.items()}
    else:
        roots = {t['id']: t['id'] for t in tasks}
        def find(key):
            while roots[key] != key:
                key = roots[key]
            return key
        for t in tasks:
            for dep in t['deps']:
                roots[find(t['id'])] = find(dep)
        parents = {t['id']: 'g-' + find(t['id']) for t in tasks}
        groups = {key: [] for key in sorted(set(parents.values()))}
    return groups, parents


class SessionBridge:
    def __init__(self, directory):
        self.bridge = Bridge(directory, timeout_ms=12000)
    def __enter__(self):
        return self.bridge
    def __exit__(self, *args):
        self.bridge.close()


def run_rollout(directory, policy, case):
    validate(policy)
    tasks, plan = case['tasks'], 'rollout'
    groups, parents = assignment(tasks, policy['grouping'])
    children = {t['id']: [] for t in tasks}
    lookup = {t['id']: t for t in tasks}
    for task in tasks:
        for dep in task['deps']:
            children[dep].append(task['id'])
    def critical(key):
        return lookup[key]['delay_ms'] + max((critical(k) for k in children[key]), default=0)
    with SessionBridge(directory) as bridge:
        forms = [f'(jiti_plan:create {binary(plan)} {binary("Empirical candidate")})',
                 f'(jiti_plan:add {binary(plan)} #B("root") \'none #B("Root") \'group () 0 #B() \'none)']
        for name, deps in groups.items():
            forms.append(f'(jiti_plan:add {binary(plan)} {binary(name)} #B("root") {binary(name)} \'group {literal(deps)} 0 #B() \'none)')
        for task in tasks:
            name = task['id']
            expected = task['left'] * task['right'] + 1
            # Verifier derives truth from the retained fixture, never a model grade.
            check = f'(=:= (map-get (map-get (map-get (map-get (jiti_plan:inspect {binary(plan)}) \'nodes) {binary(name)}) \'job) \'result) {binary(f"#(ok {expected})")})'
            source = f'(timer:sleep {task["delay_ms"]}) (+ (* {task["left"]} {task["right"]}) 1)'
            priority = critical(name) if policy['priority'] == 'critical_path' else 0
            forms.append(f'(jiti_plan:add {binary(plan)} {binary(name)} {binary(parents[name])} {binary(name)} \'task {literal(task["deps"])} {priority} {binary(check)} (map \'adapter \'lfe \'source {binary(source)} \'timeout_ms 3000))')
        execute(bridge, '\n'.join(forms))
        started = time.monotonic()
        trace, launched, peak = [], set(), 0
        while time.monotonic() - started < 15:
            execute(bridge, f'(jiti_plan:reconcile {binary(plan)})')
            state = bridge.request('plan_status', id=plan)
            if state['status'] != 'ok':
                raise FrontendError('Plan observation failed.')
            pending_checks = [n for n in state['nodes'] if n['status'] == 'awaiting_verification']
            for node in pending_checks:
                execute(bridge, f'(jiti_plan:verify {binary(plan)} {binary(node["id"])} {state["plan_version"]})')
                state = bridge.request('plan_status', id=plan)
                trace.append({'event': 'verified', 'task': node['id']})
            if all(n['status'] == 'done' for n in state['nodes']):
                elapsed = round((time.monotonic() - started) * 1000, 3)
                assert launched == set(lookup), (launched, set(lookup))
                return dict(accepted=True, elapsed_ms=elapsed, tasks=len(launched),
                            group_nodes=1+len(groups), peak_jobs=peak, trace=trace,
                            fixture_hash=digest(case), final_revision=bridge.revision,
                            store=str(Path(directory).resolve()))
            if any(n['status'] in ('failed', 'interrupted', 'cancelled') for n in state['nodes']):
                raise FrontendError('A rollout job failed; artifact was not accepted.')
            running = sum(n['kind'] == 'task' and n['status'] == 'running' for n in state['nodes'])
            for name in state['ready'][:max(0, policy['width'] - running)]:
                assert name not in launched
                # Check precedence independently of jiti_plan's ready implementation.
                done = {n['id'] for n in state['nodes'] if n['status'] == 'done'}
                assert set(lookup[name]['deps']) <= done
                execute(bridge, f'(jiti_plan:launch {binary(plan)} {binary(name)} {state["plan_version"]})')
                launched.add(name)
                running += 1
                peak = max(peak, running)
                trace.append({'event': 'launched', 'task': name, 'precedence_verified': True})
                state = bridge.request('plan_status', id=plan)
            time.sleep(.005)
        raise FrontendError('Bounded rollout deadline exceeded.')


def tool(name, description, properties):
    return dict(type='function', name=name, description=description, strict=True,
                parameters=dict(type='object', properties=properties, required=list(properties),
                                additionalProperties=False))


TOOL_DEFS = {
    'contract': tool('contract', 'Inspect the owner-controlled scheduling semantics and evaluator.', {}),
    'trace': tool('trace', 'Retrieve a real serial baseline execution trace on a public case.', {}),
    'probe': tool('probe', 'Execute one policy on a public case in the actual LFE runtime. At most two probes.', {
        'grouping': {'type': 'string', 'enum': CONTRACT['grouping']},
        'priority': {'type': 'string', 'enum': CONTRACT['priority']},
        'width': {'type': 'integer', 'enum': [1, 2]}}),
}


class Capture:
    def __init__(self):
        self.messages, self.results = [], []
    def text(self, text):
        self.messages.append(text)
    def result(self, result):
        self.results.append(result)


class CandidateChat(Chat):
    def __init__(self, bridge, grants, baseline_trace, directory, model, allowance=6):
        capture = Capture()
        super().__init__(bridge, capture, model, tool_limit=allowance, timeout=90)
        self.grants = tuple(grants)
        self.tools = [TOOL_DEFS[key] for key in grants]
        self.instructions = ('You are independent replaceable cognition for a durable Jiti farm actor. '
            'Propose a scheduling policy from the supplied sealed schema. No fixed agent-role hierarchy. '
            'Use outcomes to decide whether grouping or additional tools help. Tools are real gated actions. '
            'You cannot alter capabilities, actor identity, evaluator, task source, or resource limits. '
            'Finish with ONLY one JSON object with exactly grouping, priority, width. '
            'No code, markdown, invented measured results, hidden cases or model-training claims.')
        self.baseline_trace, self.directory = baseline_trace, directory
        self.probes, self.tool_events = 0, []

    def _response(self):
        if self.request_count >= 4:
            raise FrontendError('Actor Responses request allocation exhausted; no retry.')
        return super()._response()

    def _tool(self, call):
        name = call.get('name')
        # This dispatch check is the grant boundary, independent of advertisement.
        if name not in self.grants:
            raise FrontendError('Actor tool grant denied.')
        try:
            arguments = json.loads(call.get('arguments', ''))
        except (ValueError, TypeError):
            raise FrontendError('Malformed typed child-tool request.') from None
        if not isinstance(arguments, dict):
            raise FrontendError('Child-tool arguments must be an object.')
        if name in ('contract', 'trace'):
            if arguments:
                raise FrontendError('This read-only child tool takes no arguments.')
            result = CONTRACT if name == 'contract' else self.baseline_trace
        else:
            validate(arguments)
            if self.probes >= 2:
                raise FrontendError('Actor probe allocation exhausted.')
            self.probes += 1
            result = run_rollout(self.directory / f'probe-{self.probes}', arguments, fixture(17))
        self.tool_events.append({'tool': name, 'arguments': arguments, 'result': result})
        return {'status': 'ok', 'evidence': result}


def propose(bridge, grants, baseline, directory, model, inherited=None):
    chat = CandidateChat(bridge, grants, baseline, directory, model)
    prompt = {'schema': {k: CONTRACT[k] for k in POLICY_FIELDS},
              'job_contract': 'DAG arithmetic tasks; strict precedence; independently verified results.',
              'resource_cap': 2, 'public_case': fixture(17), 'inherited': inherited,
              'question': 'Choose a policy to test on unseen tasks; optional tool use consumes your allowance.'}
    chat.turn(json.dumps(prompt))
    try:
        policy = validate(json.loads(chat.output.messages[-1]))
    except (IndexError, ValueError, TypeError):
        raise FrontendError('Actor did not return one valid policy object.') from None
    return dict(policy=policy, model=chat.model, response_requests=chat.request_count,
                usage=chat.usage, tool_events=chat.tool_events, tools=list(grants))


def persist(bridge, key, value):
    execute(bridge, f'(state-put {binary(key)} {literal(value)})')


def evaluate(directory, policy, cases):
    results = [run_rollout(directory / f'case-{i}', policy, case) for i, case in enumerate(cases)]
    return {'accepted': all(r['accepted'] for r in results), 'cases': results,
            'elapsed_ms': round(sum(r['elapsed_ms'] for r in results), 3),
            'verified_tasks': sum(r['tasks'] for r in results)}


def save(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with open(temporary, 'w', encoding='utf-8') as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, indent=2, ensure_ascii=True)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    temporary.replace(path)


def render(path, report):
    rows = []
    def row(values):
        return '<tr>' + ''.join('<td>' + html.escape(str(value)) + '</td>' for value in values) + '</tr>'
    baseline = report.get('baseline', {})
    rows.append(row(('serial baseline', 'common', 'none', BASELINE,
                     baseline.get('verified_tasks', 0), baseline.get('elapsed_ms', 'unknown'), 'accepted')))
    for actor in report['actors']:
        evaluation = actor.get('evaluation', {})
        proposal = actor.get('proposal', {})
        rows.append(row((
            actor['id'], 'fresh' if 'parent' in actor else 'common', ', '.join(actor['tools']) or 'none', proposal.get('policy', 'failed'),
            evaluation.get('verified_tasks', 0), evaluation.get('elapsed_ms', 'unknown'),
            actor.get('error', 'accepted' if evaluation.get('accepted') else 'unknown'))))
    selection = report.get('selection', {})
    if 'parent_fresh' in selection:
        fresh = selection['parent_fresh']
        rows.append(row((selection['parent']+' parent comparison', 'fresh', 'same parent grants',
                         'same parent policy', fresh['verified_tasks'], fresh['elapsed_ms'], 'accepted')))
    summary = {key: selection[key] for key in ('parent', 'basis', 'allocation', 'improved_on_fresh', 'uncertainty') if key in selection}
    body = f'''<!doctype html><meta charset="utf-8"><title>Jiti empirical farm</title>
<style>body{{font:16px system-ui;background:#111b21;color:#e3eceb;margin:40px;max-width:1200px}}
h1{{color:#9fe1ce}}table{{border-collapse:collapse;width:100%}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #45575e}}a{{color:#9fe1ce}}pre{{white-space:pre-wrap}}</style>
<h1>Jiti empirical farm</h1><p>Real supervised identities · independent model proposals · actual LFE jobs</p>
<p>Compare elapsed times within the same dataset: the six variants share common cases;
the descendant and its parent comparison share a separate fresh set. Tool grants vary by actor.
This is a narrow local experiment. No learned dynamics model or general team improvement is established.</p>
<table><tr><th>Actor</th><th>Dataset</th><th>Granted tools</th><th>Policy</th><th>Verified jobs</th><th>Elapsed ms</th><th>Outcome</th></tr>{''.join(rows)}</table>
<h2>Allocation and descendant</h2><pre>{html.escape(json.dumps(summary, indent=2))}</pre>
<p><a href="report.json">Full receipts, artifacts and lineage</a> ·
<a href="../../../../agent-farm/docs/VIDEO_GROUNDED_FARM_DESIGN.md">Video farm design</a></p>'''
    path.write_text(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', required=True, help='existing owned agents.erl loopback longname')
    parser.add_argument('--model', required=True, help='exact previously verified Responses model')
    parser.add_argument('--output', default='.jiti/rollouts/'+time.strftime('%Y%m%d-%H%M%S'))
    parser.add_argument('--continue-retained', action='store_true', help='explicitly continue a stopped experiment; reuse retained proposals only')
    args = parser.parse_args()
    if not args.node.endswith('@127.0.0.1') or not args.node.replace('_', '').replace('@', '').replace('.', '').isalnum():
        parser.error('node must be a loopback longname with ordinary identifier characters')
    output = Path(args.output).resolve()
    if output.exists() and not args.continue_retained:
        parser.error('output already exists; inspect it. No automatic experiment replay.')
    output.mkdir(mode=0o700, parents=True, exist_ok=args.continue_retained)
    report = dict(version=1, experiment='jiti-scheduling-tool-ablation', started=time.time(),
                  video_notes='agent-farm/docs/VIDEO_GROUNDED_FARM_DESIGN.md', model=args.model,
                  max_concurrent_models=2, actor_decisions=7, max_responses_requests=28, actors=[],
                  billing='configured Responses lane; token usage retained; monetary charges unknown')
    continuation = args.continue_retained
    if continuation:
        report = json.loads((output/'report.json').read_text())
        if report.get('status') in ('completed', 'no_eligible_candidate'):
            parser.error('experiment is terminal; do not replay it')
        report['continuation'] = {'reason': 'explicit continuation after receipt serialization failure',
                                  'missing_prior_proposals': 'unknown; they are not treated as successes',
                                  'prior_request_upper_bound': 24, 'additional_request_upper_bound': 20}
        report['max_responses_requests'] = 48
        cases = json.loads((output/'private-evaluation-inputs.json').read_text())
        baseline = json.loads((output/'baseline-public.json').read_text())
    else:
        cases = [fixture(seed) for seed in (1083, 5407, 9011)]
        save(output/'private-evaluation-inputs.json', cases)
        baseline = run_rollout(output/'baseline-public', BASELINE, fixture(17))
        save(output/'baseline-public.json', baseline)
        report['baseline'] = evaluate(output/'baseline-heldout', BASELINE, cases)
    with SessionBridge(output/'population') as owner:
        for index, grants in enumerate(BUNDLES):
            identity = f'variant-{index+1}'
            source = (f'(state-put {binary(identity)} (element 2 (jiti_processes:start '
                      f'(map \'adapter \'agent \'node \'{args.node} \'logical_id {binary(identity)} '
                      f'\'name {binary("Jiti empirical " + identity)} \'tools {literal(list(grants))}))))')
            execute(owner, source)
            attested = execute(owner, f'(=:= (map-get (state-get {binary(identity)}) \'tools) {literal(list(grants))})')
            assert attested['value'] == 'true', 'Remote actor grants did not match the admitted bundle.'
            if not continuation:
                report['actors'].append(dict(id=identity, tools=list(grants),
                                            actor_handle=owner.request('execute', source=f'(state-get {binary(identity)})')['value']))
        save(output/'report.json', report)
        # Only independent cognition is concurrent. Owner mutations stay serial.
        def candidate(actor):
            directory = output/actor['id']/('decision-' + str(time.time_ns()))
            save(directory/'reservation.json', {'actor':actor['id'], 'max_responses_requests':4,
                                                'tools':actor['tools'], 'status':'reserved'})
            with SessionBridge(directory/'cognition') as bridge:
                proposal = propose(bridge, actor['tools'], baseline, directory, args.model)
                save(directory/'proposal.json', proposal)
                return proposal
        pending = [actor for actor in report['actors'] if 'proposal' not in actor]
        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(candidate, actor) for actor in pending]
            for actor, future in zip(pending, futures):
                try:
                    actor['proposal'] = future.result()
                except (FrontendError, OSError, AssertionError) as error:
                    actor['error'] = str(error)
                persist(owner, 'result/'+actor['id'], actor)
                save(output/'report.json', report)
                print(actor['id'] + ': proposal ' + ('received' if 'proposal' in actor else 'failed'), flush=True)
        for actor in report['actors']:
            if 'proposal' in actor and 'evaluation' not in actor:
                try:
                    actor['evaluation'] = evaluate(output/actor['id']/'heldout', actor['proposal']['policy'], cases)
                except (FrontendError, OSError, AssertionError) as error:
                    actor['error'] = str(error)
            persist(owner, 'result/'+actor['id'], actor)
            save(output/'report.json', report)
        eligible = [a for a in report['actors'] if a.get('evaluation', {}).get('accepted')]
        if eligible:
            selected = min(eligible, key=lambda a: (a['evaluation']['elapsed_ms'], a['id']))
            selection = dict(parent=selected['id'], basis='all outputs accepted; least observed elapsed time on common cases',
                             evidence_hash=digest(selected['evaluation']), allocation='one extra child proposal and three fresh rollouts',
                             uncertainty='single small comparison; elapsed differences may be noise; no default promotion')
            report['selection'] = selection
            child = dict(id='descendant-1', tools=selected['tools'], parent=selected['id'])
            execute(owner, f'(state-put {binary(child["id"])} (element 2 (jiti_processes:start (map \'adapter \'agent \'node \'{args.node} \'logical_id {binary(child["id"])} \'tools {literal(child["tools"])}))))')
            try:
                with SessionBridge(output/child['id']/'cognition') as bridge:
                    child['proposal'] = propose(bridge, child['tools'], baseline, output/child['id'], args.model,
                                                 inherited=dict(parent=selected['id'], policy=selected['proposal']['policy'],
                                                                outcomes=selected['evaluation']))
                fresh = [fixture(seed) for seed in (2731, 8017, 14009)]
                save(output/'private-descendant-inputs.json', fresh)
                child['evaluation'] = evaluate(output/child['id']/'heldout', child['proposal']['policy'], fresh)
                selection['parent_fresh'] = evaluate(output/'parent-fresh', selected['proposal']['policy'], fresh)
                selection['child_fresh'] = child['evaluation']
                selection['improved_on_fresh'] = child['evaluation']['elapsed_ms'] < selection['parent_fresh']['elapsed_ms']
            except (FrontendError, OSError, AssertionError) as error:
                child['error'] = str(error)
            report['actors'].append(child)
            persist(owner, 'result/'+child['id'], child)
            persist(owner, 'selection', selection)
        report['final_revision'] = owner.revision
        report['finished'] = time.time()
        report['status'] = 'completed' if eligible else 'no_eligible_candidate'
        save(output/'report.json', report)
    render(output/'index.html', report)
    print(str(output/'index.html'), flush=True)


if __name__ == '__main__':
    main()
