"""嘟嘟可谜题求解器 —— MRV 回溯 + 前向检查

  v1: 每行/列 1 嘟嘟可, 每色 1 嘟嘟可, 互不相邻
  v2: 每行/列 2 嘟嘟可, 每色 2 嘟嘟可, 互不相邻
"""

from itertools import combinations
from typing import List, Tuple, Dict, Set, Union


class DuducoPuzzleSolver:
    def __init__(self, grid: List[List[int]], num_colors: int, version: str = "v1"):
        self.grid = grid
        self.size = len(grid)
        self.num_colors = num_colors
        self.version = version

        self.per_row_col = 2 if version == "v2" else 1
        self.per_color = 2 if version == "v2" else 1

        # 颜色 → 候选格列表
        self.color_cells: Dict[int, List[Tuple[int, int]]] = {
            c: [] for c in range(1, num_colors + 1)}
        for r in range(self.size):
            for c in range(self.size):
                self.color_cells[self.grid[r][c]].append((r, c))

        # 结果
        self.duducos: Dict[int, Union[Tuple, List]] = {}
        self.solutions: List[Dict] = []

    # ── 回溯引擎 ──────────────────────────────────────────────────

    @staticmethod
    def _neighbors(r: int, c: int, n: int) -> List[Tuple[int, int]]:
        result = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < n and 0 <= nc < n:
                    result.append((nr, nc))
        return result

    def solve(self) -> List[Dict]:
        n = self.size
        color_cells = self.color_cells
        per = self.per_row_col

        state = [[0] * n for _ in range(n)]  # 0=空 1=嘟嘟可 2=封锁
        row_cnt = [0] * n
        col_cnt = [0] * n

        # ── 合法性检查 ──

        def is_valid_cell(r, c):
            if state[r][c] != 0:
                return False
            if row_cnt[r] + 1 > per or col_cnt[c] + 1 > per:
                return False
            return True

        def is_valid_pair(p1, p2):
            if not is_valid_cell(*p1) or not is_valid_cell(*p2):
                return False
            r1, c1 = p1
            r2, c2 = p2
            if abs(r1 - r2) <= 1 and abs(c1 - c2) <= 1:
                return False
            # 同行/列需额外验证容量（两个格子共增2）
            if r1 == r2 and row_cnt[r1] + 2 > per:
                return False
            if c1 == c2 and col_cnt[c1] + 2 > per:
                return False
            return True

        # ── 放置 / 回退 ──

        def place_cell(r, c):
            state[r][c] = 1
            row_cnt[r] += 1
            col_cnt[c] += 1
            changed = []
            for nr, nc in self._neighbors(r, c, n):
                if state[nr][nc] == 0:
                    state[nr][nc] = 2
                    changed.append((nr, nc))
            return changed

        def unplace_cell(r, c, changed):
            for nr, nc in changed:
                state[nr][nc] = 0
            state[r][c] = 0
            row_cnt[r] -= 1
            col_cnt[c] -= 1

        # ── 前向检查 ──

        def forward_check():
            for i in range(n):
                avail = sum(1 for j in range(n) if state[i][j] == 0)
                if avail < per - row_cnt[i]:
                    return False
                avail = sum(1 for j in range(n) if state[j][i] == 0)
                if avail < per - col_cnt[i]:
                    return False
            return True

        # ── 回溯 ──

        solutions = []
        unplaced = set(color_cells.keys())

        if self.per_color == 1:
            # ──── v1: 每色放 1 格 ────
            def gen_valid(color):
                return [(r, c) for r, c in color_cells[color] if is_valid_cell(r, c)]

            def backtrack():
                if not unplaced:
                    sol = {}
                    for color in color_cells:
                        for r, c in color_cells[color]:
                            if state[r][c] == 1:
                                sol[color] = (r, c)
                                break
                    solutions.append(sol)
                    return

                best_color = None
                best_cells = None
                for color in unplaced:
                    cells = gen_valid(color)
                    if not cells:
                        return
                    if best_color is None or len(cells) < len(best_cells):
                        best_color = color
                        best_cells = cells

                for r, c in best_cells:
                    changed = place_cell(r, c)
                    if forward_check():
                        unplaced.remove(best_color)
                        backtrack()
                        unplaced.add(best_color)
                        if solutions:
                            return
                    unplace_cell(r, c, changed)
        else:
            # ──── v2: 每色放 2 格（不邻接对） ────
            def gen_valid(color):
                pairs = []
                for p1, p2 in combinations(color_cells[color], 2):
                    if is_valid_pair(p1, p2):
                        pairs.append((p1, p2))
                return pairs

            def backtrack():
                if not unplaced:
                    sol = {}
                    for color in color_cells:
                        placed = [(r, c) for r, c in color_cells[color]
                                  if state[r][c] == 1]
                        sol[color] = placed
                    solutions.append(sol)
                    return

                best_color = None
                best_pairs = None
                for color in unplaced:
                    pairs = gen_valid(color)
                    if not pairs:
                        return
                    if best_color is None or len(pairs) < len(best_pairs):
                        best_color = color
                        best_pairs = pairs

                for p1, p2 in best_pairs:
                    changed1 = place_cell(*p1)
                    changed2 = place_cell(*p2)
                    if forward_check():
                        unplaced.remove(best_color)
                        backtrack()
                        unplaced.add(best_color)
                        if solutions:
                            return
                    unplace_cell(*p2, changed2)
                    unplace_cell(*p1, changed1)

        if forward_check():
            backtrack()

        if solutions:
            self.duducos = solutions[0]

        self.solutions = solutions
        return solutions

    # ── 文本输出 ──────────────────────────────────────────────────

    def format_solution(self, solution: Dict) -> str:
        all_positions: Set[Tuple[int, int]] = set()
        for val in solution.values():
            if isinstance(val, list):
                all_positions.update(val)
            else:
                all_positions.add(val)

        result = []
        result.append(f"网格大小: {self.size}x{self.size}")
        result.append(f"版本: {self.version}")
        result.append(f"嘟嘟可数量: {len(all_positions)}")
        result.append("")
        result.append("解法结果（*表示嘟嘟可位置）：")
        header = "   | " + " ".join(f"{i+1:2d}" for i in range(self.size))
        result.append(header)
        result.append("---+-" + "--" * self.size)

        for r in range(self.size):
            row_str = f"{r+1:2d} | "
            for c in range(self.size):
                if (r, c) in all_positions:
                    row_str += " * "
                else:
                    row_str += f"{self.grid[r][c]:2d} "
            result.append(row_str)

        if len(all_positions) <= 100:
            result.append("")
            result.append("嘟嘟可位置详情：")
            for color in sorted(solution.keys()):
                val = solution[color]
                if isinstance(val, list):
                    pos_strs = [f"({r+1}, {c+1})" for r, c in val]
                    result.append(f"  颜色{color}: {', '.join(pos_strs)}")
                else:
                    result.append(f"  颜色{color}: ({val[0]+1}, {val[1]+1})")

        return "\n".join(result)


if __name__ == "__main__":
    import sys
    import json
    if len(sys.argv) < 2:
        print("用法: python duduco_solve.py <JSON文件> [v1|v2]")
        sys.exit(1)

    version = sys.argv[2] if len(sys.argv) > 2 else "v1"
    with open(sys.argv[1], encoding='utf-8') as f:
        data = json.load(f)
    puzzle = data.get("puzzle", data)
    size = puzzle.get("size", len(puzzle["grid"]))
    grid = puzzle["grid"]
    colors = set()
    for row in grid:
        colors.update(row)

    solver = DuducoPuzzleSolver(grid, len(colors), version)
    solutions = solver.solve()
    if solutions:
        print(solver.format_solution(solutions[0]))
    else:
        print("未找到解")
