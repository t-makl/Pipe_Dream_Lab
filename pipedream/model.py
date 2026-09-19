"""1=cross; 0=double elbow. The antidiagonal is always elbow."""
from array import array
import random
import time
from .moves import GeneralMoves


class SearchExhausted(Exception):
    pass


class SearchCancelled(Exception):
    pass


def search_budget(seconds):
    if type(seconds) not in (int, float) or not 0.1 <= seconds <= 3600:
        raise ValueError('Search budget must be 0.1–3600 seconds.')
    return seconds


def size(n):
    if type(n) is not int or not 5 <= n <= 1000:
        raise ValueError('N must be an integer between 5 and 1000.')
    return n


def target(n):
    size(n)
    return [1, 2, *range(n - 2, 2, -1), n - 1, n]


def decode(n, rows):
    size(n)
    if not isinstance(rows, list) or len(rows) != n:
        raise ValueError('Expected N rows.')
    for r, row in enumerate(rows):
        if not isinstance(row, str) or len(row) != n - r or set(row) - {'0', '1'}:
            raise ValueError('Rows must be staircase strings containing only 0 and 1.')
    return [bytearray(int(t) for t in row) for row in rows]


def encode(board):
    return [''.join(map(str, row)) for row in board]


def validate(board):
    n = len(board)
    perm = list(range(1, n + 1))
    count = 0
    boundary = all(row[-1] == 0 for row in board)
    for r, row in enumerate(board):
        for c in range(len(row) - 2, -1, -1):
            if row[c]:
                i = r + c
                perm[i], perm[i + 1] = perm[i + 1], perm[i]
                count += 1
    tree = [0] * (n + 1)
    inversions = 0
    for value in reversed(perm):
        i = value - 1
        while i:
            inversions += tree[i]
            i -= i & -i
        i = value
        while i <= n:
            tree[i] += 1
            i += i & -i
    reduced = boundary and count == inversions
    matches = boundary and perm == target(n)
    return dict(valid=reduced and matches, reduced=reduced, matches_target=matches,
                boundary_valid=boundary, crosses=count, expected_crosses=(n - 4) * (n - 5) // 2,
                permutation=perm)


def trace(board, pipe):
    n = len(board)
    if type(pipe) is not int or not 1 <= pipe <= n:
        raise ValueError('Pipe must be between 1 and N.')
    r, c, horizontal = pipe - 1, 0, True
    turns, cells = [], []
    while r >= 0 and c < n - r:
        cells.append([r + 1, c + 1])
        if not board[r][c]:
            turns.append([r + 1, c + 1])
            horizontal = not horizontal
        if horizontal:
            c += 1
        else:
            r -= 1
    return dict(pipe=pipe, turns=turns, cells=cells, exit=c + 1 if r < 0 else None)


def move_count(value):
    if type(value) is not int or not 0 <= value <= 100000:
        raise ValueError('Move count must be an integer between 0 and 100000.')
    return value


def bottom_board(n):
    size(n)
    board = [bytearray(n - r) for r in range(n)]
    for r in range(2, n - 2):
        length = max(0, n - r - 3)
        board[r][:length] = b'\1' * length
    return board


def _elementary_walk(board, moves=1000, seed=None, fixed=None):
    """Apply exactly `moves` legal elementary moves, unless none are available.

    Mutates board. An indexed active list permits uniform selection among legal
    squares and O(1) local updates per move. This is NOT uniform diagram sampling.
    Fixed coordinates (e.g. a prescribed pipe) may not change.
    """
    move_count(moves)
    rng = random.Random(seed)
    fixed = fixed or {}
    stats = dict(requested=moves, applied=0, ladder=0, inverse=0, stalled=False)
    if not moves:
        return stats
    n = len(board)
    active, indexes = [], {}

    def refresh(r, c):
        if r < 0 or c < 0 or r + c > n - 3:
            return
        point = (r, c)
        legal = (not board[r][c] and not board[r+1][c+1]
                 and board[r+1][c] != board[r][c+1]
                 and (r+1, c) not in fixed and (r, c+1) not in fixed)
        if legal and point not in indexes:
            indexes[point] = len(active)
            active.append(point)
        elif not legal and point in indexes:
            i = indexes.pop(point)
            last = active.pop()
            if i < len(active):
                active[i] = last
                indexes[last] = i

    for r in range(n - 2):
        for c in range(n - r - 2):
            refresh(r, c)
    for _ in range(moves):
        if not active:
            stats['stalled'] = True
            break
        r, c = active[rng.randrange(len(active))]
        stats['ladder' if board[r+1][c] else 'inverse'] += 1
        board[r+1][c] ^= 1
        board[r][c+1] ^= 1
        stats['applied'] += 1
        # Only squares containing one of the two changed tiles can change legality.
        for rr, cc in ((r,c-1),(r,c),(r+1,c-1),(r+1,c),(r-1,c),(r-1,c+1),(r,c+1)):
            refresh(rr, cc)
    return stats


def move_mode(value):
    if value not in ('general', 'elementary'):
        raise ValueError('Move mode must be general or elementary.')
    return value


def randomize_board(board, moves=1000, seed=None, fixed=None, mode='general'):
    """Successful-move walk; general mode includes ladder/chute moves of all sizes."""
    move_count(moves)
    move_mode(mode)
    if mode == 'elementary':
        stats = _elementary_walk(board, moves, seed, fixed)
        return dict(stats, mode=mode, chute=0, non_elementary=0,
                    inverse_ladder=stats['inverse'], inverse_chute=0)
    stats = dict(requested=moves, applied=0, ladder=0, chute=0, inverse=0,
                 inverse_ladder=0, inverse_chute=0, non_elementary=0,
                 stalled=False, mode=mode)
    if not moves:
        return stats
    rng = random.Random(seed)
    legal = GeneralMoves(board, fixed)
    for _ in range(moves):
        if not legal.active:
            stats['stalled'] = True
            break
        kind, long_move = legal.apply(legal.active[rng.randrange(len(legal.active))])
        stats[kind] += 1
        stats['inverse'] += kind.startswith('inverse_')
        stats['non_elementary'] += long_move
        stats['applied'] += 1
    return stats


def random_board(n, seed=None, moves=1000, mode='general'):
    """Bottom RC graph followed by a user-sized random walk; NOT uniform."""
    board = bottom_board(n)
    randomize_board(board, moves, seed, mode=mode)
    return board


def pipe_constraints(n, pipe, turns):
    size(n)
    if type(pipe) is not int or not 1 <= pipe <= n:
        raise ValueError('Pipe must be between 1 and N.')
    if not isinstance(turns, list) or len(turns) != 5:
        raise ValueError('Supply exactly five ordered turn coordinates.')
    for point in turns:
        if (not isinstance(point, list) or len(point) != 2 or
                any(type(v) is not int for v in point) or
                not 1 <= point[0] <= n or not 1 <= point[1] <= n + 1 - point[0]):
            raise ValueError('Every turn must be an integer coordinate inside the staircase.')
    fixed = {}
    r, c, horizontal = pipe, 1, True
    for tr, tc in turns:
        if (horizontal and (tr != r or tc < c)) or (not horizontal and (tc != c or tr > r)):
            raise ValueError('Turns must alternate east and north along the pipe, without repeats.')
        while (r, c) != (tr, tc):
            fixed[r - 1, c - 1] = 1
            if horizontal:
                c += 1
            else:
                r -= 1
        fixed[r - 1, c - 1] = 0
        horizontal = not horizontal
        if horizontal:
            c += 1
        else:
            r -= 1
    if horizontal or c != target(n)[pipe - 1]:
        raise ValueError('The final vertical segment must exit at w(pipe).')
    while r >= 1:
        fixed[r - 1, c - 1] = 1
        r -= 1
    if any(r < 0 or c < 0 or r + c >= n or (r + c == n - 1 and v)
           for (r, c), v in fixed.items()):
        raise ValueError('The requested pipe leaves the staircase or crosses its elbow boundary.')
    return fixed


def constrained_board(n, pipe, turns, seed=None, seconds=180.0, cancel=None):
    """Greedy completion in both directions, then exact reduced-subword search.

    Exhaustive failure proves impossibility; timeout never does. No polynomial
    runtime guarantee for prescribed-pipe search, including at N=1000.
    """
    search_budget(seconds)
    fixed = pipe_constraints(n, pipe, turns)
    rng = random.Random(seed)
    deadline = time.monotonic() + seconds

    def check_budget():
        if cancel is not None and cancel.is_set():
            raise SearchCancelled('Search cancelled; feasibility is unknown.')
        if time.monotonic() >= deadline:
            raise SearchExhausted('Search budget exhausted; feasibility is unknown. Increase the search time.')

    check_budget()
    candidate = bottom_board(n)
    if all(candidate[r][c] == v for (r, c), v in fixed.items()):
        return candidate
    positions = [(r, c) for r in range(n) for c in range(n - r - 2, -1, -1)]
    m = len(positions)
    required = bytearray(fixed.get(p, 2) for p in positions)
    # Most feasible prescriptions complete by taking every available descent.
    # Try both word directions; w0,2 is its own inverse. Failure here is only
    # heuristic failure and must never be reported as proof of impossibility.
    directions = [False, True]
    rng.shuffle(directions)
    for reverse in directions:
        residual = target(n)
        candidate = [bytearray(n-r) for r in range(n)]
        remaining = (n - 4) * (n - 5) // 2
        for step, i in enumerate(range(m-1,-1,-1) if reverse else range(m)):
            if step % 1024 == 0:
                check_budget()
            r, c = positions[i]
            s = r + c
            descent = residual[s] > residual[s+1]
            if required[i] == 1 and not descent:
                break
            if descent and required[i] != 0:
                residual[s], residual[s+1] = residual[s+1], residual[s]
                candidate[r][c] = 1
                remaining -= 1
        else:
            if remaining == 0:
                check_budget()
                return candidate
    check_budget()
    capacity = array('I', [0]) * (m + 1)
    mandatory = array('I', [0]) * (m + 1)
    for i in range(m - 1, -1, -1):
        capacity[i] = capacity[i + 1] + (required[i] != 0)
        mandatory[i] = mandatory[i + 1] + (required[i] == 1)
    remaining = (n - 4) * (n - 5) // 2
    residual = target(n)
    chosen = bytearray(m)
    alternatives = bytearray(m)
    depth, fresh, steps = 0, True, 0
    while True:
        steps += 1
        if steps % 1024 == 0:
            check_budget()
        if depth == m and remaining == 0:
            board = [bytearray(n - r) for r in range(n)]
            for i, (r, c) in enumerate(positions):
                board[r][c] = chosen[i]
            return board
        # Future rows cannot touch already-finished permutation positions.
        row = positions[depth][0] if depth < m else n - 1
        frozen_ok = row == 0 or residual[row-1] == row
        if depth < m and frozen_ok and mandatory[depth] <= remaining <= capacity[depth]:
            r, c = positions[depth]
            s = r + c
            if fresh:
                options = []
                if required[depth] != 1:
                    options.append(0)
                if required[depth] != 0 and residual[s] > residual[s + 1]:
                    options.append(1)
                # Randomly omitting 10% of possible crosses made the old search
                # branch exponentially even when a greedy completion existed.
                if len(options) == 2:
                    options.reverse()
                alternatives[depth] = sum(1 << x for x in options)
                preferred = options[0] if options else 0
            else:
                preferred = 1 if alternatives[depth] & 2 else 0
            if alternatives[depth]:
                chosen[depth] = preferred
                alternatives[depth] &= ~(1 << preferred)
                if preferred:
                    residual[s], residual[s + 1] = residual[s + 1], residual[s]
                    remaining -= 1
                depth += 1
                fresh = True
                continue
        if depth == 0:
            raise ValueError('No reduced pipe dream contains this exact pipe (exhaustive search).')
        depth -= 1
        if chosen[depth]:
            r, c = positions[depth]
            s = r + c
            residual[s], residual[s + 1] = residual[s + 1], residual[s]
            remaining += 1
        fresh = False
