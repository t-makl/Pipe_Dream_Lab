import itertools
import threading
import time
import unittest
from unittest.mock import patch

from pipedream.model import (constrained_board, validate, trace, target,
                             SearchExhausted, SearchCancelled, search_budget)


class CompletionSearchTests(unittest.TestCase):
    def test_original_n100_prescription(self):
        turns = [[39,19],[19,19],[19,39],[1,39],[1,62]]
        started = time.perf_counter()
        for seed in (0,42):
            board = constrained_board(100,39,turns,seed=seed,seconds=5)
            self.assertTrue(validate(board)['valid'])
            self.assertEqual(trace(board,39)['turns'],turns)
        print(f'\nOriginal N=100 prescription, two seeds + validation: {time.perf_counter()-started:.4f}s')

    def test_exhaustive_n7_prescriptions(self):
        n = 7
        feasible = set()
        positions = [(r,c) for r in range(n) for c in range(n-r-1)]
        for crosses in itertools.combinations(positions,3):
            board = [bytearray(n-r) for r in range(n)]
            for r,c in crosses:
                board[r][c] = 1
            if validate(board)['valid']:
                for p in range(1,n+1):
                    turns = trace(board,p)['turns']
                    if len(turns)==5:
                        feasible.add((p,tuple(map(tuple,turns))))
        for p in range(3,n+1):
            end = target(n)[p-1]
            for upper,lower in itertools.combinations(range(1,p),2):
                for left,right in itertools.combinations(range(1,end),2):
                    turns = [[p,left],[lower,left],[lower,right],[upper,right],[upper,end]]
                    if (p,tuple(map(tuple,turns))) in feasible:
                        board = constrained_board(n,p,turns,42,seconds=2)
                        self.assertTrue(validate(board)['valid'])
                        self.assertEqual(trace(board,p)['turns'],turns)
                    else:
                        with self.assertRaises(ValueError):
                            constrained_board(n,p,turns,42,seconds=2)

    def test_budget_validation_and_cancellation(self):
        for value in (180,600,3600,.1):
            self.assertEqual(search_budget(value),value)
        for value in (0,3601,True,None,float('nan'),float('inf')):
            with self.assertRaises(ValueError):
                search_budget(value)
        stop = threading.Event()
        stop.set()
        turns = [[5,1],[3,1],[3,3],[1,3],[1,5]]
        with self.assertRaises(SearchCancelled):
            constrained_board(9,5,turns,cancel=stop)
        with patch('pipedream.model.time.monotonic',side_effect=[0,1]):
            with self.assertRaises(SearchExhausted):
                constrained_board(9,5,turns,seconds=.1)
