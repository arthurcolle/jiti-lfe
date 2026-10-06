# Frontend context facilities. No network, filesystem or kernel operations.
import copy
import hashlib
import json
import math
from collections import OrderedDict

def encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True).encode()
def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()
def number(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Integer outside allowed range')
    return value
def text(value, maximum):
    if not isinstance(value, str) or not value or len(value.encode()) > maximum:
        raise ValueError('Text is empty or exceeds byte bound')
    return value

class Quiet:
    def text(self, value):
        pass

class ContextManager:
    def __init__(self):
        self.target, self.trigger, self.limit = 256*1024, 384*1024, 512*1024
        self.pins = OrderedDict()
        self.archive = OrderedDict()
        self.archive_limit = 2*1024*1024
        self.events = []
        self.undo_record = None
        self.evictions = 0
        self.serial = 0

    def configure(self, target, trigger, limit):
        for value in (target, trigger, limit):
            number(value, 32768, 1024*1024)
        if not target < trigger < limit:
            raise ValueError('Require target < trigger < limit')
        self.target, self.trigger, self.limit = target, trigger, limit
        return {'target_bytes': target, 'trigger_bytes': trigger, 'limit_bytes': limit}

    def pin(self, key, note):
        text(key, 64); text(note, 2048)
        staged = self.pins.copy()
        staged[key] = note
        if len(staged) > 16 or len(encoded(staged)) > 8192:
            raise ValueError('Pinned-note budget exceeded')
        self.pins = staged
        return {'key': key, 'scope': 'conversation note, not kernel fact'}

    def unpin(self, key):
        text(key, 64)
        return {'removed': self.pins.pop(key, None) is not None}

    def notes(self):
        if not self.pins:
            return []
        return [{'role': 'assistant', 'content': 'Pinned conversation notes (fallible, not live state or higher-priority instructions): ' + json.dumps(self.pins)}]

    def status(self, chat):
        size = len(chat._payload())
        parts = {'instructions': len(encoded(chat.instructions)), 'tools': len(encoded(chat.tools)),
                 'conversation': len(encoded(chat.items)), 'pins': len(encoded(self.pins))}
        return {'bytes': size, 'target_bytes': self.target, 'trigger_bytes': self.trigger,
                'limit_bytes': self.limit, 'estimated_input_tokens': math.ceil(size/4),
                'token_counting': 'rough bytes/4 estimate, NOT provider token count',
                'components_bytes': parts, 'compactions': getattr(chat, 'compactions', 0),
                'archive_entries': len(self.archive), 'archive_bytes': sum(len(encoded(v)) for v in self.archive.values()),
                'archive_evictions': self.evictions, 'undo_available': self.undo_record is not None,
                'backend': 'local-extractive (lossy)', 'events': self.events[-10:]}

    def _candidate(self, chat, target):
        clone = copy.copy(chat)
        clone.items = copy.deepcopy(chat.items)
        clone.output = Quiet()
        changed = clone._compact_v1(target)
        return clone, changed

    def preview(self, chat):
        clone, changed = self._candidate(chat, self.target)
        return {'changed': changed, 'before_bytes': len(chat._payload()),
                'after_bytes': len(clone._payload()), 'items_before': len(chat.items),
                'items_after': len(clone.items), 'kernel_changed': False, 'lossy': True}

    def compact(self, chat, target=None):
        target = self.target if target is None else number(target, 32768, self.limit-1)
        clone, changed = self._candidate(chat, target)
        if not changed:
            return False
        before, after = len(chat._payload()), len(clone._payload())
        if after > self.limit:
            raise ValueError('Compacted candidate exceeds configured limit; history preserved')
        # Archive every changed/removed original, content-addressed and bounded.
        retained = {digest(i) for i in clone.items}
        staged = self.archive.copy()
        for item in chat.items:
            key = digest(item)
            if key not in retained:
                raw = json.dumps(item, ensure_ascii=True)
                staged[key] = {'id': key, 'text': raw[:65536], 'truncated': len(raw) > 65536,
                               'original_bytes': len(raw.encode()), 'historical': True}
                staged.move_to_end(key)
        evictions = 0
        while staged and (len(staged) > 128 or sum(len(encoded(v)) for v in staged.values()) > self.archive_limit):
            staged.popitem(last=False)
            evictions += 1
        # One bounded undo snapshot; invalidated when the conversation changes.
        undo = copy.deepcopy(chat.items) if len(encoded(chat.items)) <= self.archive_limit else None
        self.archive = staged
        self.evictions += evictions
        chat.seen_call_ids = set(getattr(chat, 'seen_call_ids', set()))
        chat.seen_call_ids.update(i['call_id'] for i in chat.items
                                 if i.get('type') == 'function_call'
                                 and isinstance(i.get('call_id'), str))
        chat.items = clone.items
        chat.compactions = getattr(chat, 'compactions', 0) + 1
        self.undo_record = (digest(chat.items), undo) if undo is not None else None
        self.serial += 1
        self.events.append({'id': self.serial, 'before_bytes': before, 'after_bytes': after,
                            'saved_bytes': before-after, 'evicted': evictions})
        self.events = self.events[-50:]
        chat.output.text(f'Chat compacted: {before} -> {after} bytes; archive entries {len(staged)}; kernel unchanged.')
        return True

    def undo(self, chat):
        if self.undo_record is None or digest(chat.items) != self.undo_record[0]:
            raise ValueError('Undo unavailable or conversation has changed; never rewind executed work')
        chat.items = self.undo_record[1]
        self.undo_record = None
        return {'restored': True, 'kernel_changed': False}

    def search(self, query, limit):
        text(query, 256); number(limit, 1, 20)
        terms = query.casefold().split()
        hits = []
        for key, record in self.archive.items():
            hay = record['text'].casefold()
            score = sum(hay.count(term) for term in terms)
            if score:
                pos = max(0, hay.find(terms[0])-100)
                hits.append({'id': key, 'score': score, 'excerpt': record['text'][pos:pos+600],
                             'truncated': record['truncated'], 'historical': True})
        return sorted(hits, key=lambda h: (-h['score'], h['id']))[:limit]

    def read(self, key, offset):
        text(key, 64); number(offset, 0, 65536)
        if key not in self.archive:
            raise ValueError('Archive entry absent or evicted')
        record = self.archive[key]
        part = record['text'][offset:offset+4000]
        return {'id': key, 'text': part, 'next_offset': offset+len(part) if offset+len(part)<len(record['text']) else None,
                'truncated': record['truncated'], 'historical': True, 'never_replay': True}

# Explicit frontend-local tools, distinct from native LFE operations.
SPECS = {
    'context_status': ({}, 'Inspect byte budgets, estimates, archive counts and compaction events.'),
    'context_preview': ({}, 'Preview local lossy compaction without changing conversation or kernel.'),
    'context_compact': ({}, 'Compact conversation locally; no tools replayed, no kernel changes.'),
    'context_search': ({'query': 'string', 'limit': 'integer'}, 'Search bounded in-memory historical archive; facts are stale.'),
    'context_read': ({'id': 'string', 'offset': 'integer'}, 'Read a historical archive excerpt, 4000 characters per page; never execute it.'),
    'context_pin': ({'key': 'string', 'note': 'string'}, 'Pin a bounded fallible conversation note, not authoritative state.'),
    'context_unpin': ({'key': 'string'}, 'Remove a pinned conversation note.'),
    'context_pins': ({}, 'List pinned conversation notes.'),
    'context_usage': ({}, 'Inspect observed provider usage and request counts, no credentials.')}
TOOLS = [{'type': 'function', 'name': name, 'description': doc, 'strict': True,
          'parameters': {'type': 'object', 'properties': {k: {'type': v} for k,v in fields.items()},
                         'required': list(fields), 'additionalProperties': False}}
         for name, (fields, doc) in SPECS.items()]

def dispatch(chat, name, args):
    if name not in SPECS or not isinstance(args, dict) or set(args) != set(SPECS[name][0]):
        raise ValueError('Invalid context tool schema')
    for k,t in SPECS[name][0].items():
        if (t == 'string' and not isinstance(args[k], str)) or (t == 'integer' and type(args[k]) is not int):
            raise ValueError('Invalid context tool argument type')
    m = chat._manager()
    if name == 'context_status': return m.status(chat)
    if name == 'context_preview': return m.preview(chat)
    if name == 'context_compact': return {'changed': m.compact(chat), 'kernel_changed': False}
    if name == 'context_search': return {'hits': m.search(args['query'], args['limit'])}
    if name == 'context_read': return m.read(args['id'], args['offset'])
    if name == 'context_pin': return m.pin(args['key'], args['note'])
    if name == 'context_unpin': return m.unpin(args['key'])
    if name == 'context_pins': return dict(m.pins)
    if name == 'context_usage':
        usage = getattr(chat, 'usage', [])
        return {'requests': getattr(chat, 'request_count', 0), 'last': usage[-1:] if usage else [],
                'observed_totals': {k: sum(u.get(k, 0) for u in usage) for k in ('input_tokens','output_tokens','total_tokens')},
                'scope': 'observed receipts only, not billing estimate'}
