import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from lfe_context import Quiet, digest
from lfe_context_durable import DurableContextManager

class FakeChat:
    def __init__(self, items):
        self.items = items
        self.output = Quiet()
        self.compactions = 0
        self.instructions = ''
        self.tools = []
    def _payload(self):
        return json.dumps(self.items).encode()
    def _compact_v1(self, target):
        self.items = self.items[-1:]
        return True

class Contracts(unittest.TestCase):
    def test_reopen_evicted_full_record(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'archive.db'
            old = {'role':'user', 'content':'needle ' + 'x'*70000 + ' tail-marker'}
            chat = FakeChat([old, {'role':'user','content':'current'}])
            m = DurableContextManager(path)
            m.archive_limit = 1
            self.assertTrue(m.compact(chat))
            self.assertEqual(len(m.archive), 0)
            self.assertEqual(chat.items, [{'role':'user','content':'current'}])
            m.close()
            n = DurableContextManager(path)
            hits = n.search('needle', 2)
            self.assertEqual(hits[0]['id'], digest(old))
            offset, pieces = 0, []
            while offset is not None:
                page = n.read(digest(old), offset)
                self.assertTrue(page['historical'])
                self.assertTrue(page['never_replay'])
                pieces.append(page['text'])
                offset = page['next_offset']
            self.assertEqual(json.loads(''.join(pieces)), old)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            n.close()

    def test_quota_rollback_preserves_chat(self):
        with tempfile.TemporaryDirectory() as d:
            m = DurableContextManager(Path(d)/'archive.db', quota=4096)
            chat = FakeChat([{'role':'user','content':'small'},
                             {'role':'user','content':'x'*5000},
                             {'role':'user','content':'current'}])
            before = copy.deepcopy(chat.items)
            with self.assertRaises(ValueError): m.compact(chat)
            self.assertEqual(chat.items, before)
            self.assertEqual(chat.compactions, 0)
            self.assertEqual(m.serial, 0)
            self.assertEqual(m.db.execute('SELECT COUNT(*) FROM history').fetchone()[0], 0)
            m.close()

    def test_dedup_and_negative_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            m = DurableContextManager(Path(d)/'archive.db')
            old = {'role':'user','content':'stable needle'}
            chat = FakeChat([old, {'role':'user','content':'current'}])
            m.compact(chat)
            chat.items.insert(0, old)
            m.compact(chat)
            self.assertEqual(m.db.execute('SELECT COUNT(*) FROM history').fetchone()[0], 1)
            with self.assertRaises(ValueError): m.search('needle', True)
            with self.assertRaises(ValueError): m.read(digest(old), -1)
            with self.assertRaises(ValueError): m.read('0'*64, 0)
            m.close()

if __name__ == '__main__': unittest.main()
