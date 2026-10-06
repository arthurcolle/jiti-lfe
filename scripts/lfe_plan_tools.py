"""Typed convenience tools over the existing managed planner, not another owner."""
import time
IDENTITY = {'type': 'string', 'minLength': 1, 'maxLength': 128}
VERSION = {'type': 'integer', 'minimum': 0}
NODE_FIELDS = {
    'id': IDENTITY,
    'parent': {'type': 'string', 'maxLength': 128},
    'title': IDENTITY,
    'kind': {'type': 'string', 'enum': ['group', 'task']},
    'dependencies': {'type': 'array', 'items': IDENTITY, 'maxItems': 32},
    'priority': {'type': 'integer', 'minimum': -1000000, 'maximum': 1000000},
    'check': {'type': 'string', 'maxLength': 4096},
    'source': {'type': 'string', 'maxLength': 8192},
    'timeout_ms': {'type': 'integer', 'minimum': 1, 'maximum': 60000},
}
NODE = {'type': 'object', 'properties': NODE_FIELDS, 'required': list(NODE_FIELDS),
        'additionalProperties': False}
TARGET = {'id': IDENTITY, 'node': IDENTITY, 'expected_version': VERSION}
PLAN_TOOLS = {
    'plan_list': ({'offset': VERSION}, 'List 50 durable plans. Read-only; does not replay jobs. Start offset=0.'),
    'plan_create': ({'id': IDENTITY, 'title': IDENTITY,
                     'nodes': {'type': 'array', 'items': NODE, 'maxItems': 32}},
                    'Atomically create a plan with up to 32 nodes. Parent and dependency references may be forward references. '
                    'Use parent="" for roots. Groups have source="". A task source runs as an owned asynchronous LFE job; '
                    'source="" instead creates a manually checked task. Checks are stored read-only acceptance predicates; '
                    'execution success alone does not satisfy them. Job-local writes do not commit to the owner state.'),
    'plan_add': ({'id': IDENTITY, 'expected_version': VERSION, 'node': NODE},
                 'Add one node to an unstarted plan. Its parent/dependencies must already exist. Use the current inspected version.'),
    'plan_depend': ({**TARGET, 'dependency': IDENTITY}, 'Add a prerequisite before a plan starts. Reject cycles and stale versions.'),
    'plan_launch': (TARGET, 'Explicitly launch one ready task using its stored job source. Use current plan_version. '
                    'This starts an external job; managed rollback does not undo execution. Never automatically replay unknown jobs.'),
    'plan_reconcile': ({'id': IDENTITY, 'expected_version': VERSION},
                       'Explicitly observe existing jobs and publish their outcomes. Does not launch jobs. '
                       'Remote adoption, if present in the plan, uses the existing owner/generation checks.'),
    'plan_wait': ({'id': IDENTITY, 'expected_version': VERSION,
                   'wait_ms': {'type': 'integer', 'minimum': 0, 'maximum': 30000}},
                  'Wait up to 30 seconds outside the LFE evaluation deadline for existing jobs. '
                  'Explicitly reconcile their receipts, but never launch or verify tasks. Returns wait_timed_out if jobs remain running. '
                  'Use this instead of timer:sleep in evaluated source; waiting does not consume additional model requests.'),
    'plan_verify': (TARGET, 'Run the stored read-only check for a node, separately from execution. '
                    'The check must return true and leave managed state unchanged. Use current plan_version.'),
    'plan_control': ({**TARGET, 'action': {'type': 'string', 'enum': ['block', 'unblock', 'cancel']},
                      'reason': {'type': 'string', 'maxLength': 1024}},
                     'Block/unblock admission or explicitly cancel a node through owned job cleanup. '
                     'Blocking a group gates descendants. Cancellation is an external lifecycle action; it is not undone by rollback.'),
}


def schema(kind):
    return {'type': kind} if isinstance(kind, str) else kind


def validate(value, specification):
    s = schema(specification)
    kind = s['type']
    good = ((kind == 'string' and isinstance(value, str)) or
            (kind == 'integer' and isinstance(value, int) and not isinstance(value, bool)) or
            (kind == 'boolean' and isinstance(value, bool)) or
            (kind == 'array' and isinstance(value, list)) or
            (kind == 'object' and isinstance(value, dict)))
    if not good or ('enum' in s and value not in s['enum']):
        raise ValueError('Argument type or choice does not match the native schema.')
    if kind == 'integer':
        if value < s.get('minimum', value) or value > s.get('maximum', value):
            raise ValueError('Integer argument is outside the native bounds.')
    elif kind == 'string':
        if not s.get('minLength', 0) <= len(value) <= s.get('maxLength', len(value)):
            raise ValueError('String argument is outside the native bounds.')
    elif kind == 'array':
        if not s.get('minItems', 0) <= len(value) <= s.get('maxItems', len(value)):
            raise ValueError('Array argument exceeds the native bound.')
        if s.get('uniqueItems') and any(item in value[:i] for i, item in enumerate(value)):
            raise ValueError('Array argument contains duplicates.')
        for item in value:
            validate(item, s['items'])
    elif kind == 'object':
        if set(value) != set(s['properties']):
            raise ValueError('Argument names do not match the native schema.')
        for key, field in s['properties'].items():
            validate(value[key], field)


def validate_arguments(fields, arguments):
    validate(arguments, {'type': 'object', 'properties': fields})


def binary(value):
    # Numeric UTF-8 binary literals cannot interpolate quotes, forms or escapes.
    return '#B(' + ' '.join(str(byte) for byte in value.encode('utf-8')) + ')'


def identity(value, empty=False):
    if not (empty and value == '') and not 0 < len(value.encode('utf-8')) <= 128:
        raise ValueError('Plan identities and titles require 1–128 UTF-8 bytes.')
    return binary(value)


def node_source(plan_id, node, dependencies=True):
    for key in ('id', 'title'):
        identity(node[key])
    identity(node['parent'], empty=True)
    for dep in node['dependencies']:
        identity(dep)
    if len(set(node['dependencies'])) != len(node['dependencies']):
        raise ValueError('Node dependencies must be unique.')
    if len(node['check'].encode('utf-8')) > 4096 or len(node['source'].encode('utf-8')) > 8192:
        raise ValueError('Node source or check exceeds its byte bound.')
    if node['kind'] == 'group' and node['source']:
        raise ValueError('Group nodes cannot contain executable job source.')
    if node['kind'] == 'task' and not node['check'].strip():
        raise ValueError('Task nodes require an explicit acceptance check.')
    parent = binary(node['parent']) if node['parent'] else "'none"
    deps = '(list ' + ' '.join(binary(dep) for dep in node['dependencies']) + ')' if dependencies else '()'
    spec = (f"(map 'adapter 'lfe 'source {binary(node['source'])} 'timeout_ms {node['timeout_ms']})"
            if node['source'] else "'none")
    return (f"(jiti_plan:add {binary(plan_id)} {binary(node['id'])} {parent} {binary(node['title'])} "
            f"'{node['kind']} {deps} {node['priority']} {binary(node['check'])} {spec})")


def creation_source(arguments):
    plan_id = arguments['id']
    identity(plan_id)
    identity(arguments['title'])
    nodes = arguments['nodes']
    remaining = {node['id']: node for node in nodes}
    if len(remaining) != len(nodes):
        raise ValueError('Plan node IDs must be unique.')
    if sum(len((node['source'] + node['check']).encode('utf-8')) for node in nodes) > 64000:
        raise ValueError('The complete plan exceeds its source/check byte budget.')
    for node in nodes:
        if any(dep not in remaining for dep in node['dependencies']):
            raise ValueError('A dependency references a missing plan node.')
        if node['parent'] and node['parent'] not in remaining:
            raise ValueError('A parent references a missing plan node.')
    forms = [f"(jiti_plan:create {binary(plan_id)} {binary(arguments['title'])})"]
    added = set()
    while remaining:
        ready = sorted(key for key, node in remaining.items() if not node['parent'] or node['parent'] in added)
        if not ready:
            raise ValueError('Plan parent references contain a cycle.')
        for key in ready:
            forms.append(node_source(plan_id, remaining.pop(key), dependencies=False))
            added.add(key)
    # Install precedence only after all containment nodes exist. The kernel checks
    # combined containment/precedence wait cycles and atomically discards failures.
    for node in nodes:
        for dep in node['dependencies']:
            forms.append(f"(jiti_plan:depend {binary(plan_id)} {binary(node['id'])} {binary(dep)})")
    return '\n'.join(forms)


def plan_request(bridge, op, arguments):
    if op == 'plan_list':
        return bridge.request(op, **arguments)
    if op == 'plan_wait':
        deadline = time.monotonic() + arguments['wait_ms'] / 1000
        version = arguments['expected_version']
        polls = 0
        while True:
            result = plan_request(bridge, 'plan_reconcile',
                                  {'id': arguments['id'], 'expected_version': version})
            polls += 1
            if result['status'] != 'ok':
                return result
            running = any(node['status'] == 'running' and node['kind'] == 'task' for node in result['nodes'])
            remaining = deadline - time.monotonic()
            if not running or remaining <= 0:
                result.update(wait_timed_out=running, wait_polls=polls)
                return result
            version = result['plan_version']
            time.sleep(min(.25, remaining))
    plan_id = arguments['id']
    identity(plan_id)
    if op == 'plan_create':
        source = creation_source(arguments)
    else:
        current = bridge.request('plan_status', id=plan_id)
        if current['status'] != 'ok':
            return current
        if 'token' in current:
            return {**current, 'status': 'rejected', 'reason': 'pending_attempt'}
        version = arguments['expected_version']
        if current['plan_version'] != version:
            return {**current, 'status': 'rejected', 'reason': 'stale_plan_version'}
        plan = binary(plan_id)
        if op == 'plan_add':
            expression = node_source(plan_id, arguments['node'])
        elif op == 'plan_depend':
            expression = f"(jiti_plan:depend {plan} {identity(arguments['node'])} {identity(arguments['dependency'])})"
        elif op in ('plan_launch', 'plan_verify'):
            expression = f"(jiti_plan:{op[5:]} {plan} {identity(arguments['node'])} {version})"
        elif op == 'plan_reconcile':
            expression = f'(jiti_plan:reconcile {plan})'
        elif op == 'plan_control':
            action = arguments['action']
            reason = ' ' + binary(arguments['reason']) if action == 'block' else ''
            expression = f"(jiti_plan:{action} {plan} {identity(arguments['node'])}{reason})"
        else:
            raise ValueError('Unknown native plan action.')
        # The controller is the sole writer. Check the version again inside the
        # managed operation, rather than relying only on frontend inspection.
        source = (f"(case (=:= (map-get (jiti_plan:inspect {plan}) 'version) {version}) "
                  f"('true {expression}) (_ (error 'stale_plan_version)))")
    result = bridge.request('execute', source=source)
    if result['status'] == 'ok':
        inspection = bridge.request('plan_status', id=plan_id)
        if inspection['status'] == 'ok':
            result.update({key: inspection[key] for key in ('plan_id', 'plan_version', 'nodes', 'ready')})
        else:
            result['inspection'] = inspection
    return result
