# Frontend-only contracts: no credentials, network, or live kernel.
import sys, json, copy
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path.home() / 'dsco/jiti/scripts'))
from lfe_repl import Chat, Session, FrontendError
from types import SimpleNamespace
class Output:
    def text(self, text):
        pass
class Bridge:
    token = 123
    revision = 45
    def request(self, *args, **kwargs):
        raise AssertionError('must not contact kernel')
def chat(items):
    c = Chat.__new__(Chat)
    c.model = 'test'
    c.instructions = 'test instructions'
    c.tools = []
    c.max_output_tokens = 8192
    c.items = items
    c.bridge = Bridge()
    c.output = Output()
    return c

def run():
    c = chat([{'role': 'user', 'content': 'latest goal'},
        {'type': 'function_call', 'call_id': 'a', 'name': 'lfe_status', 'arguments': '{}'},
        {'type': 'function_call_output', 'call_id': 'a', 'output': json.dumps(
            {'status': 'paused', 'revision': 45, 'token': 123, 'state': 'x' * 700000})}])
    c._ensure_context()
    assert c.context()['bytes'] < 256 * 1024
    receipt = json.loads(c.items[-1]['output'])
    assert receipt['token'] == 123 and receipt['status'] == 'paused'
    assert c.items[0]['content'] == 'latest goal'
    assert c.items[1]['call_id'] == c.items[2]['call_id'] == 'a'
    assert c.bridge.token == 123 and c.bridge.revision == 45
    old = [{'role': 'user', 'content': 'retain this goal ' + 'x' * 350000},
           {'type': 'function_call', 'call_id': 'old', 'name': 'lfe_status', 'arguments': '{}'},
           {'type': 'function_call_output', 'call_id': 'old', 'output': '{}'},
           {'role': 'user', 'content': 'latest unicode ' + chr(9731)},
           {'role': 'assistant', 'content': 'y' * 100000}]
    c = chat(old)
    latest = copy.deepcopy(old[3:])
    c._ensure_context()
    assert c.items[1:] == latest
    assert 'retain this goal' in c.items[0]['content']
    assert not any(i.get('call_id') == 'old' for i in c.items)
    assert c.context()['bytes'] < 256 * 1024
    c = chat([{'role': 'user', 'content': chr(9731) * 100000}])
    original = copy.deepcopy(c.items)
    try:
        c._ensure_context()
    except FrontendError:
        pass
    else:
        raise AssertionError('must refuse oversized current turn')
    assert c.items == original
    c = chat([{'role': 'user', 'content': 'short'}])
    assert not c.compact()
    session = Session(c.bridge, c.output, SimpleNamespace(mode='chat'))
    session.chat = c
    assert session.run('/context') and session.run('/compact')
    assert c.bridge.token == 123
    print('OK')
if __name__ == '__main__':
    run()
