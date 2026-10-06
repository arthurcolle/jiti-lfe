import copy
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from lfe_repl import Chat, FrontendError
from lfe_context import ContextManager, Quiet

def chat(items):
    c = Chat.__new__(Chat)
    c.model = 'test'
    c.instructions = 'unchanged instructions'
    c.tools = []
    c.max_output_tokens = 8192
    c.items = items
    c.output = Quiet()
    c.context_manager = ContextManager()
    return c

def pair(n, size=2000):
    return [dict(type='function_call', call_id=str(n), name='lfe_execute',
                 arguments=json.dumps({'source': 'x'*size})),
            dict(type='function_call_output', call_id=str(n),
                 output=json.dumps(dict(status='ok', revision=n, value='x'*size)))]

c = chat([dict(role='user', content='keep the full request')] +
         [i for n in range(240) for i in pair(n)])
assert len(c._payload()) > 512*1024
original = copy.deepcopy(c.items)
preview = c._manager().preview(c)
assert preview['after_bytes'] < 256*1024 and c.items == original
c._ensure_context()
assert len(c._payload()) < 256*1024
assert c.items[0] == original[0]
assert c.instructions == 'unchanged instructions'
assert c._manager().archive and c.compactions == 1
assert '0' in c.seen_call_ids
try:
    c._accept_calls([dict(type='function_call', call_id='0')])
except FrontendError:
    pass
else:
    raise AssertionError('retired call identity was reusable')
calls = {i['call_id'] for i in c.items if i.get('type') == 'function_call'}
outputs = {i['call_id'] for i in c.items if i.get('type') == 'function_call_output'}
assert calls == outputs
# Preserve unresolved call source exactly, and latest user text including Unicode.
pending = dict(type='function_call', call_id='pending', name='lfe_execute', arguments='{"source":"never alter"}')
c = chat([dict(role='user', content='完整 request')] +
         [i for n in range(150) for i in pair(n, 4000)] + [pending])
c._ensure_context()
assert pending in c.items and c.items[0]['content'] == '完整 request'
assert len(c._payload()) < 256*1024
# Oversized completed argument, even a single exchange, is retired atomically.
c = chat([dict(role='user', content='small')] + pair(1, 700000))
c._ensure_context()
assert len(c._payload()) < 256*1024
# An irreducible user request is not silently rewritten.
c = chat([dict(role='user', content='x'*600000)])
original = copy.deepcopy(c.items)
try:
    c._ensure_context()
except FrontendError:
    assert c.items == original
else:
    raise AssertionError('oversized user input must remain intact')
print('OK')
