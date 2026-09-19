"""General ladder/chute rectangles, with inverse moves and incremental indexing.

A ladder rectangle has two columns, any height >=2, NW/SE elbows,
crosses in every interior row, and exactly one cross among SW/NE.
A chute rectangle is its transpose. Shared 2x2 moves are listed once.
"""


class GeneralMoves:
    def __init__(self, board, fixed=None):
        self.board = board
        self.n = len(board)
        self.fixed = fixed or {}
        self.active = []
        self.indexes = {}
        self.groups = {}
        for axis in (0, 1):  # 0: vertical ladder; 1: horizontal chute
            for strip in range(self.n - 1):
                self.refresh(axis, strip)

    @staticmethod
    def endpoints(key):
        axis, strip, start, end = key
        if axis == 0:
            return (end, strip), (start, strip + 1)  # SW, NE
        return (strip + 1, start), (strip, end)

    def refresh(self, axis, strip):
        if not 0 <= strip < self.n - 1:
            return
        group = (axis, strip)
        for key in self.groups.get(group, ()):
            i = self.indexes.pop(key)
            last = self.active.pop()
            if i < len(self.active):
                self.active[i] = last
                self.indexes[last] = i
        found = []
        previous = None
        first = second = 0
        for pos in range(self.n - strip - 1):
            a, b = ((self.board[pos][strip], self.board[pos][strip + 1]) if axis == 0
                    else (self.board[strip][pos], self.board[strip + 1][pos]))
            if a and b:
                continue  # Interior of a potential rectangle.
            if (previous is not None and not first and not b and second != a
                    and (axis == 0 or pos - previous > 1)):
                key = (axis, strip, previous, pos)
                sw, ne = self.endpoints(key)
                if sw not in self.fixed and ne not in self.fixed:
                    self.indexes[key] = len(self.active)
                    self.active.append(key)
                    found.append(key)
            previous, first, second = pos, a, b
        self.groups[group] = found

    def apply(self, key):
        """Apply an indexed legal move; return its direction and whether long."""
        if key not in self.indexes:
            raise ValueError('Move is not currently legal.')
        sw, ne = self.endpoints(key)
        sw_cross = self.board[sw[0]][sw[1]]
        kind = ('ladder' if sw_cross else 'inverse_ladder') if key[0] == 0 else (
            'inverse_chute' if sw_cross else 'chute')
        for r, c in (sw, ne):
            self.board[r][c] ^= 1
        affected = set()
        for r, c in (sw, ne):
            affected.update(((0,c-1),(0,c),(1,r-1),(1,r)))
        for axis, strip in sorted(affected):
            self.refresh(axis, strip)
        return kind, key[3] - key[2] > 1
