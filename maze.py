# ============================================================
#  TJ Simulator — Maze  (2x2 goal support)
# ============================================================
from collections import deque


class Maze:
    DIRS     = {'N': (-1, 0), 'S': (1, 0), 'E': (0, 1), 'W': (0, -1)}
    OPPOSITE = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}
    DIR_LIST = ['N', 'E', 'S', 'W']

    def __init__(self, cols: int, rows: int):
        self.cols = cols
        self.rows = rows
        self.walls = [
            [{d: True for d in 'NESW'} for _ in range(cols)]
            for _ in range(rows)
        ]
        self.start = (0, rows - 1)
        # goal = top-left corner of 2x2 area
        self.goal  = (max(0, cols // 2 - 1), max(0, rows // 2 - 1))
        self.flood = [[0] * cols for _ in range(rows)]

    @property
    def goal_cells(self):
        """All 4 cells that form the 2x2 goal area."""
        gc, gr = self.goal
        cells = []
        for dc in range(2):
            for dr in range(2):
                nc, nr = gc + dc, gr + dr
                if self._valid(nc, nr):
                    cells.append((nc, nr))
        return cells

    # ── wall access ──────────────────────────────────────────
    def has_wall(self, col, row, d):
        if self._valid(col, row):
            return self.walls[row][col][d]
        return True

    def set_wall(self, col, row, d, value: bool):
        if not self._valid(col, row):
            return
        self.walls[row][col][d] = value
        dr, dc = self.DIRS[d]
        nc, nr = col + dc, row + dr
        if self._valid(nc, nr):
            self.walls[nr][nc][self.OPPOSITE[d]] = value

    def toggle_wall(self, col, row, d):
        self.set_wall(col, row, d, not self.has_wall(col, row, d))

    def can_move(self, col, row, d):
        return not self.has_wall(col, row, d)

    def next_cell(self, col, row, d):
        dr, dc = self.DIRS[d]
        return col + dc, row + dr

    def _valid(self, col, row):
        return 0 <= col < self.cols and 0 <= row < self.rows

    def open_neighbours(self, col, row):
        result = []
        for d in self.DIR_LIST:
            nc, nr = self.next_cell(col, row, d)
            if self._valid(nc, nr) and self.can_move(col, row, d):
                result.append((d, nc, nr))
        return result

    # ── BFS solution ─────────────────────────────────────────
    def solve(self):
        """Return list of (col,row) from start to nearest goal cell, or None."""
        s = self.start
        goal_set = set(self.goal_cells)
        queue = deque([(s, [s])])
        seen  = {s}
        while queue:
            (c, r), path = queue.popleft()
            if (c, r) in goal_set:
                return path
            for d in self.DIR_LIST:
                nc, nr = self.next_cell(c, r, d)
                if (nc, nr) not in seen and self._valid(nc, nr) and self.can_move(c, r, d):
                    seen.add((nc, nr))
                    queue.append(((nc, nr), path + [(nc, nr)]))
        return None

    # ── Flood-fill distances ──────────────────────────────────
    def compute_flood(self):
        """BFS from all goal cells simultaneously."""
        INF = 9999
        self.flood = [[INF] * self.cols for _ in range(self.rows)]
        q = deque()
        for gc, gr in self.goal_cells:
            self.flood[gr][gc] = 0
            q.append((gc, gr))
        while q:
            c, r = q.popleft()
            for d in self.DIR_LIST:
                nc, nr = self.next_cell(c, r, d)
                if self._valid(nc, nr) and self.can_move(c, r, d):
                    if self.flood[nr][nc] > self.flood[r][c] + 1:
                        self.flood[nr][nc] = self.flood[r][c] + 1
                        q.append((nc, nr))

    # ── I/O ──────────────────────────────────────────────────
    @classmethod
    def from_map_format(cls, text: str):
        lines = text.split('\n')
        while lines and lines[-1].strip() == '':
            lines.pop()
        if len(lines) < 3:
            raise ValueError("Mapa demasiado pequeno")

        num_rows = (len(lines) - 1) // 2
        num_cols = (len(lines[0].rstrip()) - 1) // 4
        if num_rows < 1 or num_cols < 1:
            raise ValueError("Dimensiones invalidas")

        maze = cls(num_cols, num_rows)
        for r in range(num_rows):
            for c in range(num_cols):
                for d in 'NESW':
                    maze.walls[r][c][d] = False

        def char_at(line_idx, pos):
            if line_idx >= len(lines): return '+'
            line = lines[line_idx]
            return line[pos] if pos < len(line) else ' '

        for r in range(num_rows):
            tl = r * 2
            ml = r * 2 + 1
            bl = r * 2 + 2
            for c in range(num_cols):
                if char_at(tl, c * 4 + 2) != ' ':
                    maze.walls[r][c]['N'] = True
                if char_at(bl, c * 4 + 2) != ' ':
                    maze.walls[r][c]['S'] = True
                if char_at(ml, c * 4) != ' ':
                    maze.walls[r][c]['W'] = True
                if char_at(ml, (c + 1) * 4) != ' ':
                    maze.walls[r][c]['E'] = True
        return maze

    @classmethod
    def from_num_format(cls, text: str):
        lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
        cells = {}
        max_x = max_y = 0
        for line in lines:
            parts = line.split()
            if len(parts) < 6:
                continue
            x, y, n, e, s, w = (int(p) for p in parts[:6])
            cells[(x, y)] = {'N': bool(n), 'E': bool(e), 'S': bool(s), 'W': bool(w)}
            max_x = max(max_x, x)
            max_y = max(max_y, y)

        maze = cls(max_x + 1, max_y + 1)
        for (x, y), walls in cells.items():
            row = maze.rows - 1 - y
            maze.walls[row][x] = dict(walls)
        return maze

    def to_map_format(self) -> str:
        lines = []
        for r in range(self.rows):
            top = '+'
            for c in range(self.cols):
                top += '---' if self.walls[r][c]['N'] else '   '
                top += '+'
            lines.append(top)
            mid = '|' if self.walls[r][0]['W'] else ' '
            for c in range(self.cols):
                mid += '   '
                mid += '|' if self.walls[r][c]['E'] else ' '
            lines.append(mid)
        bot = '+'
        for c in range(self.cols):
            bot += '---' if self.walls[self.rows - 1][c]['S'] else '   '
            bot += '+'
        lines.append(bot)
        return '\n'.join(lines)

    def to_num_format(self) -> str:
        lines = []
        for r in range(self.rows):
            y = self.rows - 1 - r
            for c in range(self.cols):
                w = self.walls[r][c]
                lines.append(
                    f"{c} {y} {int(w['N'])} {int(w['E'])} {int(w['S'])} {int(w['W'])}"
                )
        return '\n'.join(lines)