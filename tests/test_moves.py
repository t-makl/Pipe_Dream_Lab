import itertools
import random
import unittest

from pipedream.model import bottom_board, random_board, randomize_board, validate, trace
from pipedream.moves import GeneralMoves


def diagonals(board):
    return tuple(sum(board[r][d-r] for r in range(d+1)) for d in range(len(board)))


class GeneralMoveTests(unittest.TestCase):
    def test_incremental_index_and_each_move_validity(self):
        board = bottom_board(9)
        index = GeneralMoves(board)
        rng = random.Random(5)
        kinds = set()
        for _ in range(200):
            self.assertEqual(set(index.active),set(GeneralMoves(board).active))
            for key in list(index.active):
                clone = [row[:] for row in board]
                check = GeneralMoves(clone)
                check.apply(key)
                self.assertTrue(validate(clone)['valid'])
                self.assertIn(key, check.indexes)  # Every move has its inverse.
                check.apply(key)
                self.assertEqual(clone,board)
            kind, _ = index.apply(rng.choice(index.active))
            kinds.add(kind)
        self.assertEqual(kinds,{'ladder','chute','inverse_ladder','inverse_chute'})

    def test_full_small_state_space_reachable(self):
        # All three-cross subsets at N=7: compare independently validated graphs
        # with the entire component reached by general moves from the bottom.
        n = 7
        expected = set()
        positions = [(r,c) for r in range(n) for c in range(n-r-1)]
        for crosses in itertools.combinations(positions,3):
            board = [bytearray(n-r) for r in range(n)]
            for r,c in crosses:
                board[r][c] = 1
            if validate(board)['valid']:
                expected.add(tuple(map(bytes,board)))
        start = tuple(map(bytes,bottom_board(n)))
        reached, pending = {start}, [start]
        while pending:
            board = list(map(bytearray,pending.pop()))
            index = GeneralMoves(board)
            for key in list(index.active):
                copy = [row[:] for row in board]
                GeneralMoves(copy).apply(key)
                state = tuple(map(bytes,copy))
                if state not in reached:
                    reached.add(state)
                    pending.append(state)
        self.assertEqual(reached,expected)
        self.assertGreater(len({diagonals(list(map(bytearray,b))) for b in reached}),1)

    def test_sampler_leaves_elementary_component(self):
        bottom = bottom_board(9)
        board = [row[:] for row in bottom]
        stats = randomize_board(board,1000,42)
        self.assertGreater(stats['non_elementary'],0)
        self.assertNotEqual(diagonals(board),diagonals(bottom))
        self.assertTrue(validate(board)['valid'])
        elementary = random_board(9,42,moves=1000,mode='elementary')
        self.assertEqual(diagonals(elementary),diagonals(bottom))

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):
            random_board(9,mode='unknown')

    def test_generated_separated_turns(self):
        board = random_board(12,1,moves=2000,mode='general')
        turns = trace(board,8)['turns']
        self.assertEqual(turns,[[8,1],[6,1],[6,3],[4,3],[4,5]])
        self.assertTrue(validate(board)['valid'])
        self.assertTrue(all(abs(a[0]-b[0])+abs(a[1]-b[1])>1 for a,b in zip(turns,turns[1:])))
