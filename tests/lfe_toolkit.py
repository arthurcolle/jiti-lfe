#!/usr/bin/env python3
"""Real BEAM scenarios for typed operations, ownership, rollback and discovery."""
import contextlib
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from lfe_repl import Bridge, Chat, FrontendError, TOOLS
from lfe_toolkit import TOOLKIT_TOOLS

SEEN = set()


def cognition(bridge):
    chat = Chat.__new__(Chat)
    chat.bridge, chat.tools = bridge, TOOLS
    return chat


def tool(chat, op, **args):
    SEEN.add(op)
    return chat._tool({'name': 'lfe_' + op, 'arguments': json.dumps(args)})


def edit(chat, op, **args):
    args.setdefault('expected_revision', chat.bridge.revision)
    if 'preview' in TOOLKIT_TOOLS[op][0]:
        args.setdefault('preview', False)
    return tool(chat, op, **args)


def good(result):
    assert result['status'] == 'ok', result
    return result['data']


def rejected(result, code, revision):
    assert result['status'] == 'rejected' and result['reason'] == code, result
    assert result['revision'] == revision and 'token' not in result, result


def value(chat, key, kind='binary'):
    data = good(tool(chat, 'state_get', key=key, key_kind=kind))
    return json.loads(data['value_json']) if data['found'] and data['json_available'] else data


def state_scenarios(base):
    with contextlib.closing(Bridge(base / 'state')) as b:
        c = cognition(b)
        assert not good(tool(c, 'state_get', key='absent', key_kind='atom'))['found']
        good(edit(c, 'state_put', key='count', key_kind='binary', value_json='4'))
        rev = b.revision
        good(edit(c, 'state_increment', key='count', key_kind='binary', delta=3, preview=True))
        assert b.revision == rev and value(c, 'count') == 4
        good(edit(c, 'state_increment', key='count', key_kind='binary', delta=3))
        rejected(edit(c, 'state_increment', key='count', key_kind='binary', delta=3,
                      expected_revision=rev), 'stale_revision', b.revision)
        assert value(c, 'count') == 7
        rev = b.revision
        mismatch = good(edit(c, 'state_compare_set', key='count', key_kind='binary',
                             expected_json='4', value_json='9'))
        assert not mismatch['matched'] and b.revision == rev
        assert good(edit(c, 'state_compare_set', key='count', key_kind='binary',
                         expected_json='7', value_json='9'))['matched']
        good(edit(c, 'state_put', key='items', key_kind='binary', value_json='[1]'))
        good(edit(c, 'state_append', key='items', key_kind='binary', value_json='{"a":2}'))
        assert value(c, 'items') == [1, {'a': 2}]
        good(edit(c, 'state_put', key='long-list', key_kind='binary', value_json=json.dumps(list(range(30)))))
        view = good(tool(c, 'state_get', key='long-list', key_kind='binary'))
        assert view['value_truncated'] and len(json.loads(view['value_json'])) == 30
        good(edit(c, 'state_put', key='object', key_kind='binary', value_json='{"a":1}'))
        good(edit(c, 'state_merge', key='object', key_kind='binary', value_json='{"b":2}'))
        assert value(c, 'object') == {'a': 1, 'b': 2}
        good(edit(c, 'state_put', key='no_such_atom_key', key_kind='atom', value_json='true'))
        assert value(c, 'no_such_atom_key', 'atom') is True
        injection = 'key") (state-put \'injected 1) #B("'
        good(edit(c, 'state_put', key=injection, key_kind='binary', value_json='"literal"'))
        assert value(c, injection) == 'literal'
        assert b.request('execute', source="(state-get 'injected)")['value'] == 'undefined'
        # All provisional changes disappear when a later patch action fails.
        changes = [dict(key='count', key_kind='binary', action='increment', value_json='2'),
                   dict(key='missing', key_kind='binary', action='append', value_json='5')]
        rev = b.revision
        rejected(edit(c, 'state_patch', changes=changes), 'state_key_not_found', rev)
        assert value(c, 'count') == 9
        changes[1] = dict(key='missing', key_kind='binary', action='put', value_json='5')
        good(edit(c, 'state_patch', changes=changes))
        assert value(c, 'count') == 11 and value(c, 'missing') == 5
        good(edit(c, 'state_delete', key='missing', key_kind='binary'))
        assert not good(tool(c, 'state_get', key='missing', key_kind='binary'))['found']
        rev = b.revision
        assert not good(edit(c, 'state_delete', key='missing', key_kind='binary'))['deleted']
        assert b.revision == rev
        listing = good(tool(c, 'state_list', query='count', offset=0))
        assert listing['count'] == 1 and listing['keys'][0]['key'] == 'count'
        # Unknown atom lookups must not grow the VM atom table (warm path first).
        for i in range(3):
            tool(c, 'state_get', key=f'warm-not-interned-{i}', key_kind='atom')
        before = b.request('execute', source="(erlang:system_info 'atom_count)")['value']
        for i in range(20):
            assert not good(tool(c, 'state_get', key=f'never-intern-{i}', key_kind='atom'))['found']
        after = b.request('execute', source="(erlang:system_info 'atom_count)")['value']
        assert after == before, (before, after)


def define(c, name, arguments, body, **args):
    return edit(c, 'function_define', name=name, arguments=arguments, body=body,
                documentation='Typed test definition', **args)


def function_scenarios(base):
    with contextlib.closing(Bridge(base / 'functions')) as b:
        c = cognition(b)
        good(define(c, 'sum-two', ['a', 'b'], '(+ a b)'))
        assert json.loads(good(edit(c, 'function_call', name='sum-two', args_json='[3,4]'))['value_json']) == 7
        rev = b.revision
        cases = [dict(args_json='[3,4]', expected_json='7'), dict(args_json='[-1,1]', expected_json='0')]
        assert good(tool(c, 'function_test', name='sum-two', cases=cases))['passed']
        cases[0]['expected_json'] = '8'
        assert not good(tool(c, 'function_test', name='sum-two', cases=cases))['passed']
        assert b.revision == rev
        good(define(c, 'writer', [], "(state-put 'test-mutated 99) 5"))
        rev = b.revision
        result = good(tool(c, 'function_test', name='writer', cases=[dict(args_json='[]', expected_json='5')]))
        assert not result['passed'] and not result['cases'][0]['managed_unchanged']
        assert b.revision == rev and not good(tool(c, 'state_get', key='test-mutated', key_kind='atom'))['found']
        good(edit(c, 'function_call', name='writer', args_json='[]', preview=True))
        assert b.revision == rev
        good(edit(c, 'function_call', name='writer', args_json='[]'))
        assert value(c, 'test-mutated', 'atom') == 99
        rev = b.revision
        assert good(tool(c, 'expression_check', source="'true"))['passed']
        assert not good(tool(c, 'expression_check', source="(state-put 'check-mutated 1) 'true"))['passed']
        assert not good(tool(c, 'expression_check', source='(error \'private-condition)'))['passed']
        assert b.revision == rev and not good(tool(c, 'state_get', key='check-mutated', key_kind='atom'))['found']
        rejected(define(c, 'state-get', ['x'], 'x'), 'reserved_function', rev)
        rejected(define(c, 'invalid', ['x'], '(+ x unbound)'), 'invalid_definition', rev)
        # Caller checks are enforced at both adapter and native boundary.
        good(define(c, 'caller', ['a'], '(sum-two a 1)'))
        rev = b.revision
        rejected(edit(c, 'function_forget', name='sum-two', arity=2, allow_callers=False), 'function_has_callers', rev)
        assert len(good(tool(c, 'function_search', query='caller', offset=0))['functions']) == 1
        good(edit(c, 'function_forget', name='sum-two', arity=2, allow_callers=True))
        assert b.request('describe', name='caller', arity=1)['found']
        rejected(edit(c, 'function_call', name='sum-two', args_json='[1,2]'), 'function_not_found', b.revision)
        # Definition names/parameters are structured symbols, not code fragments.
        odd = 'x) (state-put \'forged 1)'
        good(define(c, odd, ['x'], 'x'))
        assert json.loads(good(edit(c, 'function_call', name=odd, args_json='["hello"]'))['value_json']) == 'hello'
        assert not good(tool(c, 'state_get', key='forged', key_kind='atom'))['found']
        # The source reader returns every page, including beyond the old 4096 cap.
        long_body = '(list ' + ' '.join(str(n) for n in range(1500)) + ')'
        good(define(c, 'long-source', [], long_body))
        chunks, offset = [], 0
        while True:
            data = good(tool(c, 'function_source', name='long-source', arity=0, offset=offset))
            chunks.append(data['source'])
            if data['next_offset'] is None:
                break
            assert data['next_offset'] > offset
            offset = data['next_offset']
        assert len(chunks) > 1 and len(''.join(chunks)) == data['characters'] and '1499' in ''.join(chunks)


def job_note_scenarios(base):
    store = base / 'jobs-notes'
    with contextlib.closing(Bridge(store)) as b:
        c = cognition(b)
        rev = b.revision
        saved = good(edit(c, 'note_put', id='decision', text='Remember actual results: 42', tags=['results', 'LFE']))
        assert saved['written_from_revision'] == rev
        good(edit(c, 'note_put', id='preview', text='discard me', tags=[], preview=True))
        assert tool(c, 'note_get', id='preview')['status'] == 'rejected'
        assert good(tool(c, 'note_search', query='RESULTS', offset=0))['count'] == 1
        assert good(tool(c, 'note_list', offset=0))['notes'][0]['id'] == 'decision'
        good(edit(c, 'note_put', id='delete-me', text='tmp', tags=[]))
        assert good(edit(c, 'note_delete', id='delete-me'))['deleted']
        start = good(edit(c, 'job_start', id='answer', source='(timer:sleep 400) 42', timeout_ms=2000))
        handle = start['recorded_handle']['id']
        assert start['observed_status'] == 'running'
        rev = b.revision
        again = good(edit(c, 'job_start', id='answer', source='(timer:sleep 400) 42', timeout_ms=2000))
        assert again['reused'] and again['recorded_handle']['id'] == handle and b.revision == rev
        rejected(edit(c, 'job_start', id='answer', source='43', timeout_ms=2000), 'job_id_conflict', rev)
        assert good(tool(c, 'job_list', offset=0))['count'] == 1
        assert tool(c, 'job_wait', id='answer', wait_ms=0, expected_revision=rev)['wait_timed_out']
        finished = good(edit(c, 'job_wait', id='answer', wait_ms=2000))
        assert finished['recorded_status'] == 'succeeded' and finished['recorded_handle']['result'] == '#(ok 42)'
        good(edit(c, 'job_reconcile', id='answer'))
        # Background code cannot publish managed changes.
        good(edit(c, 'job_start', id='mutating', source="(state-put 'job-mutated 1) 5", timeout_ms=2000))
        failed = good(edit(c, 'job_wait', id='mutating', wait_ms=2000))
        assert failed['recorded_status'] == 'failed' and not good(tool(c, 'state_get', key='job-mutated', key_kind='atom'))['found']
        good(edit(c, 'job_start', id='cancel', source='(timer:sleep 3000) 0', timeout_ms=4000))
        stopped = good(edit(c, 'job_cancel', id='cancel'))
        assert stopped['recorded_status'] == 'stopped'
        rev = b.revision
        good(edit(c, 'job_cancel', id='cancel'))
        assert b.revision == rev
        rejected(edit(c, 'job_wait', id='cancel', wait_ms=30000, expected_revision=rev-1), 'stale_revision', rev)
        # Retain an outstanding handle across a real VM restart.
        unknown = good(edit(c, 'job_start', id='outstanding', source='(timer:sleep 3000) 9', timeout_ms=4000))
        old_handle = unknown['recorded_handle']['id']
    with contextlib.closing(Bridge(store)) as b:
        c = cognition(b)
        assert good(tool(c, 'note_get', id='decision'))['text'] == 'Remember actual results: 42'
        observed = good(tool(c, 'job_status', id='outstanding'))
        assert observed['observed_status'] == 'unknown' and observed['recorded_status'] == 'running'
        repeated = good(edit(c, 'job_start', id='outstanding', source='(timer:sleep 3000) 9', timeout_ms=4000))
        assert repeated['reused'] and repeated['recorded_handle']['id'] == old_handle
        rejected(edit(c, 'job_cancel', id='outstanding'), 'job_handle_unknown', b.revision)
        terminal = good(edit(c, 'job_reconcile', id='answer'))
        assert terminal['recorded_status'] == 'succeeded' and terminal['observed_status'] == 'unknown'
        assert terminal['recorded_handle']['result'] == '#(ok 42)'
        assert b.request('execute', source='(length (jiti_processes:all))')['value'] == '0'


def effects_and_safety(base):
    # Even an external launch rejected at publication cannot be repeated inside
    # this owner manager. No automatic retry/recovery launch is introduced.
    with contextlib.closing(Bridge(base / 'safety', safety=['(=:= (length (jiti_processes:all)) 0)'])) as b:
        c = cognition(b)
        for _ in range(2):
            r = edit(c, 'job_start', id='blocked', source='7', timeout_ms=1000)
            rejected(r, 'safety_failed', 0)
        assert good(tool(c, 'job_list', offset=0))['runtime_job_count'] == 1
        # Read-only manager inspection bypasses no owner checks or publication.
        count = b.request('preview', source='(length (jiti_processes:all))')
        assert count['status'] == 'rejected'
        # Change the owner contract in a fresh bridge to inspect separately.
    with contextlib.closing(Bridge(base / 'rollback-job')) as b:
        c = cognition(b)
        first = good(edit(c, 'job_start', id='once', source='5', timeout_ms=1000))
        b.request('rollback', revision=0)
        second = good(edit(c, 'job_start', id='once', source='5', timeout_ms=1000))
        assert first['recorded_handle']['id'] == second['recorded_handle']['id']
        assert b.request('execute', source='(length (jiti_processes:all))')['value'] == '1'
        b.request('rollback', revision=0)
        rejected(edit(c, 'job_start', id='once', source='6', timeout_ms=1000), 'job_id_conflict', b.revision)


def discovery_and_validation(base):
    with contextlib.closing(Bridge(base / 'discovery')) as b:
        c = cognition(b)
        listing = good(tool(c, 'tools_list', query='state_', offset=0))
        assert listing['count'] == 9
        description = good(tool(c, 'tools_describe', name='lfe_state_put'))
        assert description['strict'] and description['parameters']['additionalProperties'] is False
        c.tools = [t for t in TOOLS if t['name'] in {'lfe_tools_list', 'lfe_tools_describe'}]
        assert good(tool(c, 'tools_list', query='', offset=0))['count'] == 2
        rejected(tool(c, 'tools_describe', name='lfe_state_put'), 'tool_not_advertised', 0)
        try:
            tool(c, 'state_get', key='hidden', key_kind='binary')
        except FrontendError:
            pass
        else:
            raise AssertionError('An unadvertised tool was dispatched.')
        c.tools = TOOLS
        found = good(tool(c, 'workspace_find', path='jiti/scripts', query='lfe_toolkit'))
        assert 'jiti/scripts/lfe_toolkit.py' in found['paths']
        searched = good(tool(c, 'workspace_search', path='jiti/scripts/lfe_toolkit.py', query='TOOLKIT_TOOLS', offset=0))
        assert searched['matches'] and searched['offsets_exact']
        # A multibyte character split across the 12000-byte read boundary is
        # reconstructed before matching, and capped matches have continuation.
        fixture = ROOT / 'tests' / 'toolkit-search-fixture.md'
        try:
            fixture.write_text('a'*11999 + 'é boundary' + (' match'*60), encoding='utf-8')
            unicode_hit = good(tool(c, 'workspace_search', path='jiti/tests/'+fixture.name,
                                    query='é boundary', offset=0))
            assert unicode_hit['matches'][0]['byte_offset'] == 11999 and unicode_hit['offsets_exact']
            first = good(tool(c, 'workspace_search', path='jiti/tests/'+fixture.name, query='match', offset=0))
            second = good(tool(c, 'workspace_search', path='jiti/tests/'+fixture.name, query='match', offset=first['next_offset']))
            assert len(first['matches']) == 50 and len(second['matches']) == 10 and second['next_offset'] is None
        finally:
            fixture.unlink(missing_ok=True)
        for path in ('../etc/passwd', '/etc/passwd', 'jiti/.env'):
            r = tool(c, 'workspace_search', path=path, query='x', offset=0)
            assert r['status'] == 'rejected', r
        cases = [dict(key='k', key_kind='binary', value_json='NaN', expected_revision=0, preview=False),
                 dict(key='k', key_kind='binary', value_json='[1', expected_revision=0, preview=False),
                 dict(key='k', key_kind='binary', value_json='1', expected_revision=True, preview=False),
                 dict(key='k', key_kind='binary', value_json='1', expected_revision=0, preview=1),
                 dict(key='k', key_kind='binary', value_json='1', expected_revision=0, preview=False, extra=True),
                 dict(key='k', key_kind='binary', value_json='1', expected_revision=0),
                 dict(key='k', key_kind='binary', value_json='"' + 'a'*32769 + '"', expected_revision=0, preview=False),
                 dict(key='k', key_kind='binary', value_json='"\\ud800"', expected_revision=0, preview=False),
                 dict(key='k', key_kind='binary', value_json='['*17+'0'+']'*17, expected_revision=0, preview=False),
                 dict(key='k', key_kind='binary', value_json=json.dumps([0]*1024), expected_revision=0, preview=False)]
        for args in cases:
            try:
                tool(c, 'state_put', **args)
            except FrontendError:
                pass
            else:
                raise AssertionError('Invalid request reached the native worker.')
        try:
            tool(c, 'function_test', name='absent', cases=[])
        except FrontendError:
            pass
        else:
            raise AssertionError('Empty test cases accepted.')
        assert b.revision == 0


def main():
    with tempfile.TemporaryDirectory(prefix='jiti-toolkit-') as temporary:
        base = Path(temporary)
        for scenario in (state_scenarios, function_scenarios, job_note_scenarios,
                         effects_and_safety, discovery_and_validation):
            scenario(base)
            print(scenario.__name__ + ': passed', flush=True)
    assert set(TOOLKIT_TOOLS) <= SEEN, set(TOOLKIT_TOOLS) - SEEN
    print(f'All {len(TOOLKIT_TOOLS)} added tools exercised against actual BEAM processes.')


if __name__ == '__main__':
    main()
