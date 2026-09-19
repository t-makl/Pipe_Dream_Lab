import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch

from pipedream.server import Store, handler
from pipedream.model import SearchCancelled


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler(Store(Path(self.tmp.name)/'db.sqlite3')))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, path, data=None):
        req = Request(self.base + path, data=None if data is None else json.dumps(data).encode(),
                      headers={'Content-Type': 'application/json'})
        with urlopen(req) as response:
            return json.load(response)

    def test_roundtrip_edit_and_errors(self):
        doc = self.request('/api/generate', {'n': 12, 'seed': 42})
        self.assertTrue(doc['validation']['valid'])
        edited = self.request('/api/toggle', dict(doc, row=1, column=1))
        self.assertFalse(edited['validation']['valid'])
        saved = self.request('/api/save', dict(edited, name='Edited research draft'))
        self.assertEqual(self.request(f'/api/saved/{saved["id"]}')['rows'], edited['rows'])
        self.assertEqual(len(self.request('/api/saved')), 1)
        result = self.request('/api/trace', dict(doc, pipe=3))
        self.assertEqual(result['exit'], 10)
        for path, body in [('/api/generate', {'n':1001}),('/api/toggle', dict(doc,row=1,column=12))]:
            with self.assertRaises(HTTPError) as caught:
                self.request(path,body)
            self.assertEqual(caught.exception.code,400)
            caught.exception.close()

    def test_static_page(self):
        with urlopen(self.base) as response:
            self.assertIn(b'Pipe Dream Lab',response.read())

    def test_long_search_budget_and_cancel(self):
        turns = [[39,19],[19,19],[19,39],[1,39],[1,62]]
        doc = self.request('/api/generate',{'n':100,'pipe':39,'turns':turns,'seconds':3600,'moves':0})
        self.assertTrue(doc['validation']['valid'])
        self.assertEqual(self.request('/api/trace',dict(doc,pipe=39))['turns'],turns)
        self.assertFalse(self.request('/api/cancel',{})['cancel_requested'])
        started = threading.Event()
        result = []

        def slow_search(*args, cancel=None, **kwargs):
            started.set()
            if not cancel.wait(5):
                raise AssertionError('Cancel did not reach active search.')
            raise SearchCancelled('Search cancelled; feasibility is unknown.')

        def request_search():
            try:
                result.append(self.request('/api/generate',{'n':100,'pipe':39,'turns':turns,'seconds':600}))
            except HTTPError as exc:
                with exc:
                    result.append(json.load(exc))

        with patch('pipedream.server.constrained_board',side_effect=slow_search):
            worker = threading.Thread(target=request_search)
            worker.start()
            try:
                self.assertTrue(started.wait(2))
                self.assertTrue(self.request('/api/cancel',{})['cancel_requested'])
            finally:
                worker.join(6)
            self.assertFalse(worker.is_alive())
            self.assertEqual(result[0]['status'],'cancelled')
        self.assertTrue(self.request('/api/generate',{'n':7,'moves':0})['validation']['valid'])

    def test_controlled_randomization(self):
        doc = self.request('/api/generate', {'n':12,'seed':42,'moves':0})
        self.assertEqual(doc['randomization']['applied'],0)
        request = dict(doc,seed=7,moves=123,annotations={'pipes':{'3':'#ff0000'}})
        changed = self.request('/api/randomize',request)
        self.assertEqual(changed['randomization']['applied'],123)
        self.assertEqual(changed['randomization']['mode'],'general')
        elementary = self.request('/api/randomize',dict(request,mode='elementary'))
        self.assertEqual(elementary['randomization']['mode'],'elementary')
        self.assertEqual(elementary['randomization']['non_elementary'],0)
        self.assertTrue(changed['validation']['valid'])
        self.assertEqual(changed['annotations']['pipes'],{'3':'#ff0000'})
        self.assertEqual(changed,self.request('/api/randomize',request))
        saved = self.request('/api/save',dict(changed,name='123 moves'))
        self.assertEqual(self.request(f'/api/saved/{saved["id"]}')['randomization'],changed['randomization'])
        for path,body in [('/api/generate',{'n':12,'moves':-1}),
                          ('/api/randomize',dict(doc,moves=100001)),
                          ('/api/randomize',dict(doc,moves=True)),
                          ('/api/generate',{'n':12,'mode':'bad'}),
                          ('/api/randomize',dict(doc,mode='bad'))]:
            with self.assertRaises(HTTPError) as caught:
                self.request(path,body)
            self.assertEqual(caught.exception.code,400)
            caught.exception.close()

    def test_prescribed_pipe_survives_randomization_and_storage(self):
        doc = self.request('/api/generate',{'n':7,'seed':42,'moves':20})
        for p in range(1,8):
            traced = self.request('/api/trace',dict(doc,pipe=p))
            if len(traced['turns'])==5:
                break
        self.assertEqual(len(traced['turns']),5)
        solved = self.request('/api/generate',{'n':7,'pipe':p,'turns':traced['turns'],'seed':5,'moves':50})
        self.assertEqual(self.request('/api/trace',dict(solved,pipe=p))['turns'],traced['turns'])
        saved = self.request('/api/save',dict(solved,name='Locked pipe'))
        loaded = self.request(f'/api/saved/{saved["id"]}')
        changed = self.request('/api/randomize',dict(loaded,moves=100,seed=17))
        self.assertEqual(changed['constraint'],solved['constraint'])
        self.assertEqual(self.request('/api/trace',dict(changed,pipe=p))['turns'],traced['turns'])


if __name__ == '__main__':
    unittest.main()
