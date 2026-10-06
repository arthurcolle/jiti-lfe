# Contract acceptance independent of compaction implementation.
import sys, json, copy
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from lfe_repl import Chat, Session, FrontendError, CONTEXT_TOOLS
from lfe_context import ContextManager, dispatch, encoded, digest
from types import SimpleNamespace
class Output:
    def __init__(self): self.messages = []
    def text(self, value): self.messages.append(value)
    def result(self, *args, **kwargs): pass
class Bridge:
    token, revision, broken = 777, 50, False
    def request(self, *args, **kwargs): raise AssertionError('unexpected kernel call')
def chat(items):
    c = Chat.__new__(Chat)
    c.model, c.instructions, c.tools = 'mock', 'base', list(CONTEXT_TOOLS)
    c.max_output_tokens, c.items = 8192, items
    c.output, c.bridge = Output(), Bridge()
    c.request_count, c.usage = 0, []
    return c

def rejects(fn, error=ValueError):
    try: fn()
    except error: return
    raise AssertionError('expected rejection')

def run():
    m = ContextManager()
    rejects(lambda: m.configure(True, 100000, 200000))
    rejects(lambda: m.configure(100000, 90000, 200000))
    rejects(lambda: m.configure(33000, 44000, 2**21))
    before = (m.target,m.trigger,m.limit)
    rejects(lambda: m.configure(1, 2, 3))
    assert before == (m.target,m.trigger,m.limit)
    c = chat([{'role': 'user', 'content': 'goal alpha ' + 'x'*400000},
              {'role': 'user', 'content': 'current precise request'}])
    m = c._manager()
    m.pin('goal', 'preserve alpha goal')
    assert 'preserve alpha goal' in c._payload().decode()
    snapshot = copy.deepcopy(c.items)
    state = (copy.deepcopy(m.archive),copy.deepcopy(m.events),m.undo_record)
    preview = dispatch(c, 'context_preview', {})
    assert preview['changed'] and preview['after_bytes'] < preview['before_bytes']
    assert c.items == snapshot and state == (m.archive,m.events,m.undo_record)
    assert dispatch(c, 'context_compact', {})['changed']
    assert c.items[-1] == snapshot[-1]
    assert c.context()['bytes'] < m.trigger
    assert c.bridge.token == 777 and c.bridge.revision == 50
    hits = dispatch(c, 'context_search', {'query': 'alpha', 'limit': 3})['hits']
    assert hits and hits[0]['historical']
    page = dispatch(c, 'context_read', {'id': hits[0]['id'], 'offset': 0})
    assert len(page['text']) <= 4000 and page['truncated'] and page['never_replay']
    m.undo(c)
    assert c.items == snapshot
    rejects(lambda: m.undo(c))
    c.compact()
    c.items.append({'role':'user','content':'later action'})
    rejects(lambda: m.undo(c))
    c = chat([{'role':'user','content':'current'},
        {'type':'function_call','call_id':'a','name':'lfe_status','arguments':'{}'},
        {'type':'function_call_output','call_id':'a','output':json.dumps({'status':'paused','token':777,'revision':50,'state':'z'*600000})}])
    c._accept_calls([])
    c.compact()
    assert json.loads(c.items[-1]['output'])['token'] == 777
    assert c.items[1]['call_id'] == c.items[2]['call_id']
    rejects(lambda: c._accept_calls([{'call_id':'a'}]), FrontendError)
    rejects(lambda: c._accept_calls([{'call_id':'b'},{'call_id':'c'}]), FrontendError)
    rejects(lambda: c._accept_calls([{'call_id':''}]), FrontendError)
    c._accept_calls([{'call_id':'b'}])
    rejects(lambda: c._accept_calls([{'call_id':'b'}]), FrontendError)
    m = c._manager()
    for i in range(16): m.pin(str(i),'note')
    rejects(lambda: m.pin('overflow','note'))
    rejects(lambda: m.pin('big','a'*2049))
    rejects(lambda: dispatch(c,'context_search',{'query':'a','limit':True}))
    rejects(lambda: dispatch(c,'context_search',{'query':'a','limit':21}))
    rejects(lambda: dispatch(c,'context_status',{'extra':1}))
    rejects(lambda: m.read('absent',0))
    rejects(lambda: m.read('absent',-1))
    assert len(CONTEXT_TOOLS) == 9 and all(t['parameters']['additionalProperties'] is False for t in CONTEXT_TOOLS)
    c.usage = [{'input_tokens':10,'output_tokens':2},{'input_tokens':20,'total_tokens':25}]
    assert c._tool({'name':'context_usage','arguments':'{}'})['observed_totals']['input_tokens'] == 30
    rejects(lambda: c._tool({'name':'context_search','arguments':'{}'}), FrontendError)
    m.unpin(str(0))
    session = Session(c.bridge,c.output,SimpleNamespace(mode='chat'))
    session.chat = c
    for command in ('/context','/compact-preview','/pins','/usage','/context-tools','/pin example note','/unpin example','/context-budget 128 256 512'):
        assert session.run(command)
    assert session.run('/clear')
    assert c.items == [] and not c._manager().archive and not c._manager().pins
    rejects(lambda: c._accept_calls([{'call_id':'a'}]), FrontendError)
    # Failed candidate cannot publish archive, items or undo.
    c = chat([{'role':'user','content':'x'*600000}])
    snapshot = copy.deepcopy(c.items)
    rejects(lambda: c._ensure_context(), FrontendError)
    assert c.items == snapshot and not c._manager().archive
    # Archive resource bound and visible eviction, using many unique originals.
    c = chat([{'role':'user','content':str(i)+' alpha '+('q'*5000)} for i in range(160)] + [{'role':'user','content':'new'}])
    c._manager().archive_limit = 10000
    c.compact(32768)
    m = c._manager()
    assert len(m.archive) <= 128 and sum(len(encoded(v)) for v in m.archive.values()) <= 10000
    assert m.evictions > 0
    print('OK')
if __name__ == '__main__': run()
