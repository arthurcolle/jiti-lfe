# Opt-in durable historical context. Does not launch or replay work.
import copy
import json
import os
import sqlite3
from pathlib import Path
from lfe_context import ContextManager, digest, text, number

class DurableContextManager(ContextManager):
    def __init__(self, path, quota=64*1024*1024):
        super().__init__()
        number(quota, 4096, 1024*1024*1024)
        self.quota = quota
        path = Path(path)
        if path.is_symlink():
            raise ValueError('Archive symlink rejected')
        fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        os.fchmod(fd, 0o600)
        os.close(fd)
        self.db = sqlite3.connect(path, timeout=5)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS history (id TEXT PRIMARY KEY, body TEXT NOT NULL, size INTEGER NOT NULL)')
        self.db.commit()

    def close(self):
        self.db.close()

    def compact(self, chat, target=None):
        # Stage all lossy changes. Persist complete originals before publishing.
        staged = copy.copy(self)
        staged.archive = self.archive.copy()
        staged.events = list(self.events)
        clone = copy.copy(chat)
        clone.items = copy.deepcopy(chat.items)
        from lfe_context import Quiet
        clone.output = Quiet()
        if not ContextManager.compact(staged, clone, target):
            return False
        retained = {digest(i) for i in clone.items}
        originals = [(digest(i), json.dumps(i, ensure_ascii=True, sort_keys=True))
                     for i in chat.items if digest(i) not in retained]
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            used = self.db.execute('SELECT COALESCE(SUM(size),0) FROM history').fetchone()[0]
            for key, body in originals:
                if self.db.execute('SELECT 1 FROM history WHERE id=?', (key,)).fetchone():
                    continue
                size = len(body.encode())
                if used + size > self.quota:
                    raise ValueError('Durable archive quota reached; conversation preserved')
                self.db.execute('INSERT INTO history VALUES (?,?,?)', (key, body, size))
                used += size
        # Crash before this point only leaves extra historical evidence, never replay.
        self.__dict__.update(staged.__dict__)
        chat.items = clone.items
        chat.compactions = clone.compactions
        chat.output.text('Context compacted; complete originals committed to durable archive; no kernel operations replayed.')
        return True

    def search(self, query, limit):
        text(query, 256); number(limit, 1, 20)
        terms = query.casefold().split()
        hits = []
        # Streaming scan bounded by the configured logical archive quota.
        for key, body in self.db.execute('SELECT id,body FROM history'):
            hay = body.casefold()
            score = sum(hay.count(term) for term in terms)
            if score:
                positions = [hay.find(t) for t in terms if t in hay]
                pos = max(0, min(positions)-100)
                hits.append({'id': key, 'score': score, 'excerpt': body[pos:pos+600],
                             'truncated': False, 'historical': True, 'never_replay': True})
                hits.sort(key=lambda h: (-h['score'], h['id']))
                del hits[limit:]
        return hits

    def read(self, key, offset):
        text(key, 64); number(offset, 0, self.quota)
        row = self.db.execute('SELECT body FROM history WHERE id=?', (key,)).fetchone()
        if row is None:
            raise ValueError('Historical entry absent')
        body = row[0]
        if offset > len(body):
            raise ValueError('Offset beyond entry')
        part = body[offset:offset+4000]
        return {'id': key, 'text': part,
                'next_offset': offset+len(part) if offset+len(part)<len(body) else None,
                'truncated': False, 'historical': True, 'never_replay': True}

    def status(self, chat):
        result = super().status(chat)
        count, size = self.db.execute('SELECT COUNT(*),COALESCE(SUM(size),0) FROM history').fetchone()
        result.update(durable_entries=count, durable_bytes=size, durable_quota=self.quota,
                      quota_scope='logical record bytes; SQLite overhead is additional',
                      recovery_scope='historical archive only; not active chat or kernel jobs')
        return result
