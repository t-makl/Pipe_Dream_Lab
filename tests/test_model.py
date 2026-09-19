import tempfile
import itertools
import time
import unittest
from pathlib import Path

from pipedream.model import (random_board, constrained_board, validate, target, trace,
                             encode, decode, pipe_constraints, bottom_board, randomize_board)
from pipedream.server import Store, document


class MathematicsTests(unittest.TestCase):
    def test_exact_move_count_and_inverses(self):
        base = bottom_board(12)
        self.assertEqual(random_board(12,42,moves=0),base)
        one = random_board(12,42,moves=1)
        self.assertEqual(sum(a!=b for ra,rb in zip(base,one) for a,b in zip(ra,rb)),2)
        self.assertTrue(validate(one)['valid'])
        board = bottom_board(12)
        stats = randomize_board(board,2000,42)
        self.assertEqual(stats['applied'],2000)
        self.assertEqual(stats['ladder']+stats['chute']+stats['inverse'],2000)
        self.assertGreater(stats['inverse'],0)
        self.assertFalse(stats['stalled'])
        self.assertTrue(validate(board)['valid'])
        self.assertEqual(board,random_board(12,42,moves=2000))

    def test_stalled_walk_and_move_validation(self):
        board = bottom_board(5)
        stats = randomize_board(board,100,42)
        self.assertEqual(stats['applied'],0)
        self.assertTrue(stats['stalled'])
        for moves in [-1,100001,1.5,True,None]:
            with self.assertRaises(ValueError):
                randomize_board(board,moves)

    def test_random_moves_preserve_fixed_pipe(self):
        board = random_board(12,42)
        match = next((trace(board,p) for p in range(1,13) if len(trace(board,p)['turns'])==5),None)
        self.assertIsNotNone(match)
        fixed = pipe_constraints(12,match['pipe'],match['turns'])
        stats = randomize_board(board,500,7,fixed)
        self.assertEqual(trace(board,match['pipe'])['turns'],match['turns'])
        self.assertTrue(validate(board)['valid'])
        self.assertEqual(stats['applied'],500)

    def test_random_validity_and_physical_routing(self):
        for n in [5, 6, 7, 10, 30, 100]:
            for seed in range(20):
                b = random_board(n, seed)
                self.assertTrue(validate(b)['valid'], (n, seed))
                self.assertEqual([trace(b, p)['exit'] for p in range(1, n+1)], target(n))

    def test_reproducibility_and_variety(self):
        self.assertEqual(random_board(20, 42), random_board(20, 42))
        self.assertGreater(len({tuple(encode(random_board(12, i))) for i in range(10)}), 1)

    def test_known_five_turn_constraints(self):
        found = 0
        for seed in range(12):
            b = random_board(7, seed)
            for p in range(1, 8):
                turns = trace(b, p)['turns']
                if len(turns) == 5:
                    result = constrained_board(7, p, turns, seed=seed+100, seconds=2)
                    self.assertTrue(validate(result)['valid'])
                    self.assertEqual(trace(result, p)['turns'], turns)
                    found += 1
        self.assertGreater(found, 0)

    def test_exhaustive_small_diagrams(self):
        # N=6 target has one inversion. Enumerate every possible one-cross graph.
        n = 6
        valid = []
        for r in range(n):
            for c in range(n-r-1):
                b = [bytearray(n-i) for i in range(n)]
                b[r][c] = 1
                if validate(b)['valid']:
                    valid.append(b)
        self.assertEqual(len(valid), 3)
        for b in valid:
            for p in range(1, n+1):
                turns = trace(b, p)['turns']
                if len(turns) == 5:
                    solved = constrained_board(n, p, turns, 101)
                    self.assertTrue(validate(solved)['valid'])
                    self.assertEqual(trace(solved, p)['turns'], turns)
        # Exhaust every geometrically possible five-turn input at N=6,
        # comparing solver feasibility against the full set of valid graphs.
        for p in range(3, n+1):
            end = target(n)[p-1]
            for lower, upper in itertools.combinations(range(1,p),2):
                for first, middle in itertools.combinations(range(1,end),2):
                    turns = [[p,first],[upper,first],[upper,middle],[lower,middle],[lower,end]]
                    feasible = any(trace(b,p)['turns']==turns for b in valid)
                    if feasible:
                        solved = constrained_board(n,p,turns,99)
                        self.assertEqual(trace(solved,p)['turns'],turns)
                    else:
                        with self.assertRaises(ValueError):
                            constrained_board(n,p,turns,99)

    def test_edit_invalidates_target(self):
        b = random_board(10, 10)
        b[0][0] ^= 1
        self.assertFalse(validate(b)['valid'])
        b[0][0] ^= 1
        self.assertTrue(validate(b)['valid'])
        b[0][-1] = 1
        self.assertFalse(validate(b)['boundary_valid'])

    def test_input_rejection(self):
        for n in [4, 1001, 6.0, True, None]:
            with self.assertRaises(ValueError):
                random_board(n)
        with self.assertRaises(ValueError):
            decode(6, ['0'])
        with self.assertRaises(ValueError):
            pipe_constraints(10, 3, [[3, 1]]*5)

    def test_n1000(self):
        start = time.perf_counter()
        b = random_board(1000, 42)
        self.assertTrue(validate(b)['valid'])
        self.assertEqual(sum(map(len,b)), 500500)
        self.assertEqual(decode(1000, encode(b)), b)
        print(f'\nN=1000 generation + validation + serialization: {time.perf_counter()-start:.3f}s')

    def test_store_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'test.sqlite3'
            store = Store(path)
            doc = document(random_board(12, 5), annotations={'pipes': {'3': '#ff0000'}})
            identifier = store.save('Research example', doc)
            self.assertEqual(Store(path).load(identifier), doc)
            self.assertEqual(store.list()[0]['name'], 'Research example')


if __name__ == '__main__':
    unittest.main()
