"""Dependency-free, loopback-only HTTP API and SQLite persistence."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from contextlib import contextmanager
import argparse
import json
import re
import secrets
import sqlite3
import threading
import zlib

from .model import (decode, encode, bottom_board, randomize_board, move_count, move_mode,
                    pipe_constraints, constrained_board, validate, trace, SearchExhausted,
                    SearchCancelled, search_budget)

ROOT = Path(__file__).resolve().parent.parent
GENERATION_LOCK = threading.Lock()
SEARCH_ACTIVE = threading.Event()
SEARCH_CANCEL = threading.Event()


class Store:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS diagrams (id INTEGER PRIMARY KEY, name TEXT NOT NULL, '
                       'n INTEGER NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP, payload BLOB NOT NULL)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, name, document):
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
            raise ValueError('Name must contain 1–120 characters.')
        payload = zlib.compress(json.dumps(document).encode())
        with self.connect() as db:
            cur = db.execute('INSERT INTO diagrams(name,n,payload) VALUES(?,?,?)',
                             (name.strip(), document['n'], payload))
            return cur.lastrowid

    def list(self):
        with self.connect() as db:
            return [dict(id=i, name=name, n=n, created=created) for i, name, n, created in
                    db.execute('SELECT id,name,n,created FROM diagrams ORDER BY id DESC')]

    def load(self, identifier):
        with self.connect() as db:
            row = db.execute('SELECT payload FROM diagrams WHERE id=?', (identifier,)).fetchone()
        if row is None:
            raise ValueError('Saved diagram not found.')
        return json.loads(zlib.decompress(row[0]))


def document(board, **extra):
    return dict(n=len(board), rows=encode(board), validation=validate(board), **extra)


def clean_annotations(value, n):
    if not isinstance(value, dict):
        raise ValueError('Annotations must be an object.')
    result = {}
    for category in ('pipes', 'rows', 'columns'):
        mapping = value.get(category, {})
        if not isinstance(mapping, dict):
            raise ValueError('Annotation categories must be objects.')
        result[category] = {}
        for key, color in mapping.items():
            if (not key.isdecimal() or not 1 <= int(key) <= n or not isinstance(color, str)
                    or not re.fullmatch(r'#[0-9a-fA-F]{6}', color)):
                raise ValueError('Annotations need indexes 1 through N and six-digit hex colors.')
            result[category][str(int(key))] = color
    return result


def constraint_metadata(data, board):
    constraint = data.get('constraint')
    if constraint is None:
        return None, {}
    if not isinstance(constraint, dict):
        raise ValueError('Constraint must be an object.')
    fixed = pipe_constraints(len(board), constraint.get('pipe'), constraint.get('turns'))
    if any(board[r][c] != v for (r, c), v in fixed.items()):
        raise ValueError('The diagram does not contain its prescribed pipe.')
    return dict(pipe=constraint['pipe'], turns=constraint['turns']), fixed


def request_seed(data):
    seed = data.get('seed')
    if seed is not None and type(seed) is not int:
        raise ValueError('Seed must be an integer.')
    return secrets.randbits(32) if seed is None else seed


def handler(store):
    class Handler(BaseHTTPRequestHandler):
        def json_response(self, data, status=200):
            payload = json.dumps(data).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            try:
                path = self.path.split('?')[0]
                if path == '/api/saved':
                    return self.json_response(store.list())
                if path.startswith('/api/saved/'):
                    return self.json_response(store.load(int(path.rsplit('/', 1)[1])))
                files = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
                         '/style.css': ('style.css', 'text/css')}
                if path not in files:
                    return self.json_response({'error': 'Not found'}, 404)
                name, mime = files[path]
                payload = (ROOT / 'static' / name).read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', mime + '; charset=utf-8')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except (ValueError, TypeError) as exc:
                self.json_response({'error': str(exc)}, 400)

        def do_POST(self):
            try:
                # Reject browser requests initiated by unrelated origins.
                origin = self.headers.get('Origin')
                if origin and origin != 'http://' + self.headers.get('Host', ''):
                    return self.json_response({'error': 'Origin rejected'}, 403)
                if not self.headers.get('Content-Type', '').startswith('application/json'):
                    raise ValueError('Content-Type must be application/json.')
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 4_000_000:
                    raise ValueError('Request must be between 1 byte and 4 MB.')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Expected a JSON object.')
                if self.path == '/api/cancel':
                    active = SEARCH_ACTIVE.is_set()
                    if active:
                        SEARCH_CANCEL.set()
                    return self.json_response({'cancel_requested': active})
                if self.path == '/api/generate':
                    seed = request_seed(data)
                    moves = move_count(data.get('moves', 1000))
                    mode = move_mode(data.get('mode', 'general'))
                    if not GENERATION_LOCK.acquire(blocking=False):
                        return self.json_response({'error': 'Another generation is running.'}, 409)
                    try:
                        constraint, fixed = None, {}
                        if data.get('turns') is not None:
                            seconds = search_budget(data.get('seconds', 180))
                            SEARCH_CANCEL.clear()
                            SEARCH_ACTIVE.set()
                            try:
                                board = constrained_board(data.get('n'), data.get('pipe'), data['turns'],
                                                          seed, seconds, cancel=SEARCH_CANCEL)
                            finally:
                                SEARCH_ACTIVE.clear()
                            constraint = dict(pipe=data['pipe'], turns=data['turns'])
                            _, fixed = constraint_metadata({'constraint': constraint}, board)
                        else:
                            board = bottom_board(data.get('n'))
                        stats = randomize_board(board, moves, seed, fixed, mode)
                        result = document(board, seed=seed, annotations={}, randomization=stats, constraint=constraint)
                        if not result['validation']['valid']:
                            raise RuntimeError('Generator failed its independent validity check.')
                        return self.json_response(result)
                    finally:
                        GENERATION_LOCK.release()
                board = decode(data.get('n'), data.get('rows'))
                colors = clean_annotations(data.get('annotations', {}), len(board))
                constraint, fixed = constraint_metadata(data, board)
                if self.path == '/api/randomize':
                    seed = request_seed(data)
                    moves = move_count(data.get('moves', 1000))
                    mode = move_mode(data.get('mode', 'general'))
                    if not validate(board)['valid']:
                        raise ValueError('Random moves require a valid reduced diagram. Undo invalid tile edits first.')
                    if not GENERATION_LOCK.acquire(blocking=False):
                        return self.json_response({'error': 'Another generation is running.'}, 409)
                    try:
                        stats = randomize_board(board, moves, seed, fixed, mode)
                        result = document(board, seed=seed, annotations=colors, randomization=stats, constraint=constraint)
                        if not result['validation']['valid']:
                            raise RuntimeError('Random moves failed the validity check.')
                        return self.json_response(result)
                    finally:
                        GENERATION_LOCK.release()
                if self.path == '/api/trace':
                    return self.json_response(trace(board, data.get('pipe')))
                if self.path == '/api/toggle':
                    r, c = data.get('row'), data.get('column')
                    if type(r) is not int or type(c) is not int or not (1 <= r <= len(board) and 1 <= c <= len(board[r - 1])):
                        raise ValueError('Tile coordinate outside staircase.')
                    if c == len(board[r - 1]):
                        raise ValueError('The antidiagonal boundary must remain elbow tiles.')
                    board[r - 1][c - 1] ^= 1
                    # Manual tile edits intentionally release the prescribed-pipe lock.
                    return self.json_response(document(board, annotations=colors, seed=data.get('seed')))
                if self.path == '/api/validate':
                    return self.json_response(document(board, annotations=colors, seed=data.get('seed'),
                                                       constraint=constraint, randomization=data.get('randomization')))
                if self.path == '/api/save':
                    result = document(board, annotations=colors, seed=data.get('seed'),
                                      constraint=constraint, randomization=data.get('randomization'))
                    return self.json_response({'id': store.save(data.get('name'), result)})
                return self.json_response({'error': 'Not found'}, 404)
            except SearchExhausted as exc:
                self.json_response({'error': str(exc), 'status': 'unknown'}, 408)
            except SearchCancelled as exc:
                self.json_response({'error': str(exc), 'status': 'cancelled'}, 409)
            except (ValueError, TypeError, KeyError) as exc:
                self.json_response({'error': str(exc)}, 400)
            except Exception:
                import traceback
                traceback.print_exc()
                self.json_response({'error': 'Internal server error; see server console.'}, 500)
    return Handler


def serve():
    parser = argparse.ArgumentParser(description='Local Pipe Dream Lab')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--db', type=Path, default=ROOT / 'diagrams.sqlite3')
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(Store(args.db)))
    print(f'Pipe Dream Lab: http://127.0.0.1:{args.port}  (Ctrl+C to stop)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
