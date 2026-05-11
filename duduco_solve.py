from collections import defaultdict
from typing import List, Tuple, Set, Dict


class DuducoPuzzleSolver:
    """嘟嘟可谜题求解器。
    核心策略：约束传播(4条规则迭代至不动点) + 双色迷你回溯 + 主递归回溯。
    
    数据结构：
    - duducos: 已确认的嘟嘟可位置 {颜色号: (行,列)}
    - no_duduco_rows/cols: 已被占用的行/列
    - no_duduco_positions: 被排除的格子(嘟嘟可相邻8格等)
    - current_placement: 回溯时的临时放置"""

    def __init__(self, grid: List[List[int]], num_colors: int):
        self.grid = grid
        self.size = len(grid)
        if self.size > 15:
            raise ValueError(f"网格大小 {self.size} 超过上限 15")
        self.num_colors = num_colors
        self.regions = self._find_regions()
        self.solutions = []
        self.current_placement = {}
        self.duducos = {}
        self.no_duduco_rows = set()
        self.no_duduco_cols = set()
        self.no_duduco_positions = set()

    def solve(self):
        """主求解入口：约束传播 → 双色回溯穿插 → 主递归回溯"""
        self._detection_loop()
        while self._mini_backtrack_two_colors():
            self._detection_loop()
        self._solve_region(len(self.duducos))
        return self.solutions

    def format_solution(self, solution: Dict[int, Tuple[int, int]]) -> str:
        """将解法格式化为可读文本：网格可视化 + 按行排序的坐标列表"""
        result = []
        result.append(f"网格大小: {self.size}x{self.size}")
        result.append(f"嘟嘟可数量: {len(solution)}")
        result.append("")

        result.append("解法结果（*表示嘟嘟可位置）：")
        header = "   | " + " ".join(f"{i+1:2d}" for i in range(self.size))
        result.append(header)
        result.append("---+-" + "--" * self.size)

        for r in range(self.size):
            row_str = f"{r+1:2d} | "
            for c in range(self.size):
                pos = (r, c)
                if pos in solution.values():
                    row_str += " * "
                else:
                    row_str += f"{self.grid[r][c]:2d} "
            result.append(row_str)

        result.append("")
        result.append("嘟嘟可位置详情：")
        for color, (r, c) in sorted(solution.items(), key=lambda x: x[1][0]):
            result.append(f"  颜色{color}: ({r+1}, {c+1})")

        return "\n".join(result)

    def _find_regions(self) -> Dict[int, List[Tuple[int, int]]]:
        """BFS连通域分析：为每种颜色找出所有连通块"""
        visited, regions = set(), defaultdict(list)
        for r in range(self.size):
            for c in range(self.size):
                if (r, c) not in visited:
                    color = self.grid[r][c]
                    regions[color].append(self._bfs_region(r, c, color, visited))
        return regions

    def _bfs_region(self, start_r: int, start_c: int, color: int, visited: Set[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """BFS搜索单个颜色的连通区域（4方向）"""
        region, queue, directions = [], [(start_r, start_c)], [(-1, 0), (1, 0), (0, -1), (0, 1)]
        while queue:
            r, c = queue.pop(0)
            if (r, c) in visited or self.grid[r][c] != color:
                continue
            visited.add((r, c))
            region.append((r, c))
            for dr, dc in directions:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.size and 0 <= nc < self.size and (nr, nc) not in visited:
                    if self.grid[nr][nc] == color:
                        queue.append((nr, nc))
        return region

    def _is_valid_position(self, r: int, c: int) -> bool:
        """检查(r,c)是否仍是合法的嘟嘟可候选位置"""
        return (r not in self.no_duduco_rows and
                c not in self.no_duduco_cols and
                (r, c) not in self.no_duduco_positions)

    def _mark_placement(self, color: int, pos: Tuple[int, int]):
        """确认放置：记录嘟嘟可位置，排除同行、同列、周围8格"""
        r, c = pos
        self.duducos[color] = pos
        self.no_duduco_rows.add(r)
        self.no_duduco_cols.add(c)
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.size and 0 <= nc < self.size:
                    self.no_duduco_positions.add((nr, nc))

    def _detect_last_cell(self) -> bool:
        """规则1·最后一格：某行/某列只剩1个合法格子 → 必为嘟嘟可"""
        for r in range(self.size):
            if r in self.no_duduco_rows:
                continue
            candidates = [(r, c) for c in range(self.size) if c not in self.no_duduco_cols and (r, c) not in self.no_duduco_positions]
            if len(candidates) == 1:
                r, c = candidates[0]
                color = self.grid[r][c]
                if color not in self.duducos and color not in self.current_placement:
                    self._mark_placement(color, candidates[0])
                    return True

        for c in range(self.size):
            if c in self.no_duduco_cols:
                continue
            candidates = [(r, c) for r in range(self.size) if self._is_valid_position(r, c)]
            if len(candidates) == 1:
                r, c = candidates[0]
                color = self.grid[r][c]
                if color not in self.duducos and color not in self.current_placement:
                    self._mark_placement(color, candidates[0])
                    return True
        return False

    def _detect_n_color_shared_rows(self, n: int) -> bool:
        """规则2·鸽巢原理（双向）：
        N种颜色的候选位置仅跨N行(或N列) →
          a) 那N行/列上其他颜色的格子排除（鸽子不够，占位排除）
          b) 那N种颜色在其他行/列的格子也排除（鸽子变多，定域排除）"""
        updated = False
        colors = list(self.regions.keys())
        if len(colors) < n:
            return updated

        from itertools import combinations

        for color_combination in combinations(colors, n):
            if any(c in self.duducos or c in self.current_placement for c in color_combination):
                continue

            all_rows = set()
            for color in color_combination:
                region = self.regions[color][0]
                for pos in region:
                    r, c = pos
                    if self._is_valid_position(r, c):
                        all_rows.add(r)

            if len(all_rows) == n:
                for r in all_rows:
                    for c in range(self.size):
                        color_at_pos = self.grid[r][c]
                        if color_at_pos not in color_combination:
                            pos = (r, c)
                            if pos not in self.no_duduco_positions:
                                self.no_duduco_positions.add(pos)
                                updated = True
                for color in color_combination:
                    for pos in self.regions[color][0]:
                        rr, cc = pos
                        if rr not in all_rows and self._is_valid_position(rr, cc):
                            self.no_duduco_positions.add((rr, cc))
                            updated = True

        for color_combination in combinations(colors, n):
            if any(c in self.duducos or c in self.current_placement for c in color_combination):
                continue

            all_cols = set()
            for color in color_combination:
                region = self.regions[color][0]
                for pos in region:
                    r, c = pos
                    if self._is_valid_position(r, c):
                        all_cols.add(c)

            if len(all_cols) == n:
                for c in all_cols:
                    for r in range(self.size):
                        color_at_pos = self.grid[r][c]
                        if color_at_pos not in color_combination:
                            pos = (r, c)
                            if pos not in self.no_duduco_positions:
                                self.no_duduco_positions.add(pos)
                                updated = True
                for color in color_combination:
                    for pos in self.regions[color][0]:
                        rr, cc = pos
                        if cc not in all_cols and self._is_valid_position(rr, cc):
                            self.no_duduco_positions.add((rr, cc))
                            updated = True
        return updated

    def _detect_surrounded_exclusion(self) -> bool:
        """规则3·包围排除：若某格子的8邻域包含了某颜色全部剩余候选格，则该格不可放嘟嘟可。
        通用规则，覆盖L形剔除、两格排除、单格排除等所有特例"""
        updated = False
        for r in range(self.size):
            for c in range(self.size):
                if not self._is_valid_position(r, c):
                    continue
                neighbors = set()
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < self.size and 0 <= nc < self.size:
                            neighbors.add((nr, nc))

                for color, regions_list in self.regions.items():
                    if color in self.duducos or color in self.current_placement:
                        continue
                    region = regions_list[0]
                    unmarked = [p for p in region if self._is_valid_position(p[0], p[1])]
                    if not unmarked:
                        continue
                    if all(p in neighbors for p in unmarked):
                        self.no_duduco_positions.add((r, c))
                        updated = True
                        break
        return updated

    def _detection_loop(self):
        """约束传播主循环：迭代3条规则直到不再产生新发现(不动点)，最多100轮"""
        max_iterations = 100
        for iteration in range(max_iterations):
            changed = False

            if self._detect_last_cell():
                changed = True
            for n in range(1, self.size + 1):
                if self._detect_n_color_shared_rows(n):
                    changed = True
            if self._detect_surrounded_exclusion():
                changed = True

            if not changed:
                break

    def _mini_backtrack_two_colors(self) -> bool:
        """双色迷你回溯：约束传播卡住时，取候选最少的2种颜色穷举所有合法组合。
        跑完约束后交叉验证——若所有分支都推导出相同的放置/排除，则这些公共发现是确定的。
        这是不完全回溯，不保存完整解，只提取公共推理结果。"""
        color_candidates = {}
        for color in self.regions:
            if color in self.duducos or color in self.current_placement:
                continue
            region = self.regions[color][0]
            valid = [pos for pos in region if self._is_valid_position(pos[0], pos[1])]
            if valid:
                color_candidates[color] = valid

        if len(color_candidates) < 2:
            return False

        sorted_colors = sorted(color_candidates.items(), key=lambda x: len(x[1]))
        (color1, positions1), (color2, positions2) = sorted_colors[0], sorted_colors[1]

        valid_combinations = []
        for pos1 in positions1:
            for pos2 in positions2:
                if pos1 == pos2:
                    continue
                r1, c1 = pos1
                r2, c2 = pos2
                # 嘟嘟可不能同行、同列、相邻
                if r1 == r2 or c1 == c2:
                    continue
                if abs(r1 - r2) <= 1 and abs(c1 - c2) <= 1:
                    continue
                valid_combinations.append((pos1, pos2))

        if not valid_combinations:
            return False

        branch_new_duducos = {}
        branch_new_no_pos = []

        for pos1, pos2 in valid_combinations:
            old_duducos = self.duducos.copy()
            old_no_rows = self.no_duduco_rows.copy()
            old_no_cols = self.no_duduco_cols.copy()
            old_no_pos = self.no_duduco_positions.copy()

            self.duducos[color1] = pos1
            self.duducos[color2] = pos2
            r1, c1 = pos1
            r2, c2 = pos2
            self.no_duduco_rows.add(r1)
            self.no_duduco_rows.add(r2)
            self.no_duduco_cols.add(c1)
            self.no_duduco_cols.add(c2)
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0:
                        continue
                    nr1, nc1 = r1 + dr, c1 + dc
                    nr2, nc2 = r2 + dr, c2 + dc
                    if 0 <= nr1 < self.size and 0 <= nc1 < self.size:
                        self.no_duduco_positions.add((nr1, nc1))
                    if 0 <= nr2 < self.size and 0 <= nc2 < self.size:
                        self.no_duduco_positions.add((nr2, nc2))

            self._detection_loop()

            new_duducos = {c: p for c, p in self.duducos.items()
                           if c not in old_duducos and c != color1 and c != color2}
            branch_new_duducos[(pos1, pos2)] = new_duducos
            branch_new_no_pos.append(self.no_duduco_positions - old_no_pos)

            self.duducos = old_duducos
            self.no_duduco_rows = old_no_rows
            self.no_duduco_cols = old_no_cols
            self.no_duduco_positions = old_no_pos

        if not branch_new_duducos:
            return False

        found = False

        branch_sets = [set(d.keys()) for d in branch_new_duducos.values()]
        common_colors = branch_sets[0]
        for s in branch_sets[1:]:
            common_colors &= s

        # 所有分支公共推导出的放置 → 确认
        if common_colors:
            for color in common_colors:
                if color in self.duducos:
                    continue
                positions = [branch[color] for branch in branch_new_duducos.values()]
                if len(set(positions)) == 1:
                    self._mark_placement(color, positions[0])
                    found = True

        if branch_new_no_pos:
            common_no = branch_new_no_pos[0].copy()
            for s in branch_new_no_pos[1:]:
                common_no &= s
            # 所有分支公共排除的格子 → 确认排除
            for pos in common_no:
                if pos not in self.no_duduco_positions:
                    self.no_duduco_positions.add(pos)
                    found = True

        return found

    def _solve_region(self, placed_count: int) -> bool:
        """主递归回溯：对剩余颜色逐一尝试合法位置，保存/恢复约束状态。
        找到第一个完整解即返回True。"""
        if placed_count >= len(self.regions):
            solution = {**self.duducos, **self.current_placement}
            self.solutions.append(solution)
            return True

        for color in sorted(self.regions.keys()):
            if color in self.duducos or color in self.current_placement:
                continue

            region = self.regions[color][0]
            valid_positions = [pos for pos in region if self._is_valid_position(pos[0], pos[1])]

            if not valid_positions:
                return False

            for pos in valid_positions:
                self.current_placement[color] = pos
                r, c = pos

                old_no_duduco_rows = self.no_duduco_rows.copy()
                old_no_duduco_cols = self.no_duduco_cols.copy()
                old_no_duduco_positions = self.no_duduco_positions.copy()

                self.no_duduco_rows.add(r)
                self.no_duduco_cols.add(c)
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < self.size and 0 <= nc < self.size:
                            self.no_duduco_positions.add((nr, nc))

                if self._solve_region(placed_count + 1):
                    return True

                self.no_duduco_rows = old_no_duduco_rows
                self.no_duduco_cols = old_no_duduco_cols
                self.no_duduco_positions = old_no_duduco_positions
                del self.current_placement[color]
        return False


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python duduco_solve.py <输入文件>")
        print("  输入文件格式：首行为网格大小，后续每行为空格分隔的颜色编号")
        print("  示例文件: test1_output.txt")
        sys.exit(1)
    with open(sys.argv[1], encoding='utf-8') as f:
        lines = f.read().strip().split('\n')
    size = int(lines[0])
    grid = []
    for line in lines[1:]:
        grid.append([int(x) for x in line.split()])
    colors = set()
    for row in grid:
        colors.update(row)
    solver = DuducoPuzzleSolver(grid, len(colors))
    solutions = solver.solve()
    if solutions:
        print(solver.format_solution(solutions[0]))
    else:
        print("未找到解")
