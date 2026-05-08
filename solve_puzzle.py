import sys
# import time  # 计时功能，需要时取消注释
from collections import defaultdict
from typing import List, Tuple, Set, Dict

class DuducoPuzzleSolver:
    def __init__(self, grid: List[List[int]], num_colors: int):
        self.grid = grid
        self.size = len(grid)
        self.num_colors = num_colors
        self.regions = self._find_regions()
        self.solutions = []
        self.current_placement = {}
        self.duducos = {}
        self.no_duduco_rows = set()
        self.no_duduco_cols = set()
        self.no_duduco_positions = set()
    
    def _is_valid_position(self, r: int, c: int) -> bool:
        return (r not in self.no_duduco_rows and 
                c not in self.no_duduco_cols and 
                (r, c) not in self.no_duduco_positions)

    def _find_regions(self) -> Dict[int, List[Tuple[int, int]]]:
        visited = set()
        regions = defaultdict(list)

        for r in range(self.size):
            for c in range(self.size):
                if (r, c) not in visited:
                    color = self.grid[r][c]
                    region = self._bfs_region(r, c, color, visited)
                    regions[color].append(region)

        return regions

    def _bfs_region(self, start_r: int, start_c: int, color: int, visited: Set[Tuple[int, int]]) -> List[Tuple[int, int]]:
        region = []
        queue = [(start_r, start_c)]
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

        while queue:
            r, c = queue.pop(0)
            if (r, c) in visited:
                continue
            if self.grid[r][c] != color:
                continue

            visited.add((r, c))
            region.append((r, c))

            for dr, dc in directions:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.size and 0 <= nc < self.size and (nr, nc) not in visited:
                    if self.grid[nr][nc] == color:
                        queue.append((nr, nc))

        return region

    def _mark_placement(self, color: int, pos: Tuple[int, int]):
        """标记嘟嘟可位置及其影响区域"""
        r, c = pos
        
        # 记录嘟嘟可位置
        self.duducos[color] = pos
        print(f"检测到嘟嘟可：颜色{color} 在位置({r},{c})")
        
        # 标记行和列为"没有嘟嘟可"
        self.no_duduco_rows.add(r)
        self.no_duduco_cols.add(c)
        
        # 标记周围8格为"没有嘟嘟可"
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.size and 0 <= nc < self.size:
                    self.no_duduco_positions.add((nr, nc))

    def _detect_last_cell(self) -> bool:
        """检测某一行或某一列是否只剩一个位置未被标记为"没有嘟嘟可"，若是则标记为嘟嘟可"""
        # 检查每一行
        for r in range(self.size):
            # 如果这一行已经有嘟嘟可，跳过
            if r in self.no_duduco_rows:
                continue
            
            # 统计这一行未被标记为"没有嘟嘟可"的格子数
            candidates = []
            for c in range(self.size):
                pos = (r, c)
                if c not in self.no_duduco_cols and pos not in self.no_duduco_positions:
                    candidates.append(pos)
            
            # 如果只剩一个候选位置
            if len(candidates) == 1:
                pos = candidates[0]
                r, c = pos
                
                # 找到这个位置所属的颜色
                color = self.grid[r][c]
                
                # 如果这个颜色还没有嘟嘟可
                if color not in self.duducos and color not in self.current_placement:
                    self._mark_placement(color, pos)
                    print(f"发现行{r}只剩一个位置({r},{c})，标记为嘟嘟可")
                    return True
        
        # 检查每一列
        for c in range(self.size):
            # 如果这一列已经有嘟嘟可，跳过
            if c in self.no_duduco_cols:
                continue
            
            # 统计这一列未被标记为"没有嘟嘟可"的格子数
            candidates = []
            for r in range(self.size):
                pos = (r, c)
                if self._is_valid_position(r, c):
                    candidates.append(pos)
            
            # 如果只剩一个候选位置
            if len(candidates) == 1:
                pos = candidates[0]
                r, c = pos
                
                # 找到这个位置所属的颜色
                color = self.grid[r][c]
                
                # 如果这个颜色还没有嘟嘟可
                if color not in self.duducos and color not in self.current_placement:
                    self._mark_placement(color, pos)
                    print(f"发现列{c}只剩一个位置({r},{c})，标记为嘟嘟可")
                    return True
        
        return False

    def _detect_n_color_shared_rows(self, n: int) -> bool:
        """检测n种颜色是否总共占据了n行（不多不少），若是则将同行中其他颜色的格子标记为"没有嘟嘟可"；列同理"""
        updated = False
        
        colors = list(self.regions.keys())
        num_colors = len(colors)
        
        if num_colors < n:
            return updated
        
        # 生成所有n种颜色的组合
        from itertools import combinations
        
        # 检查行的情况
        for color_combination in combinations(colors, n):
            # 检查是否有任何颜色已经被处理
            skip = False
            for color in color_combination:
                if color in self.duducos or color in self.current_placement:
                    skip = True
                    break
            if skip:
                continue
            
            # 获取这n种颜色所有未被标记的格子所在的行
            all_rows = set()
            for color in color_combination:
                region = self.regions[color][0]
                for pos in region:
                    r, c = pos
                    if self._is_valid_position(r, c):
                        all_rows.add(r)
            
            # 如果这n种颜色总共恰好占据n行
            if len(all_rows) == n:
                color_names = ", ".join(str(c) for c in color_combination)
                print(f"发现颜色{color_names}总共占据{n}行{all_rows}")
                
                # 将这n行中其他颜色的格子标记为"没有嘟嘟可"
                for r in all_rows:
                    for c in range(self.size):
                        color_at_pos = self.grid[r][c]
                        # 如果这个位置的颜色不在组合中，且未被标记
                        if color_at_pos not in color_combination:
                            pos = (r, c)
                            if pos not in self.no_duduco_positions:
                                self.no_duduco_positions.add(pos)
                                updated = True
                print(f"  - 将这些行中其他颜色的格子标记为'没有嘟嘟可'")
        
        # 检查列的情况
        for color_combination in combinations(colors, n):
            # 检查是否有任何颜色已经被处理
            skip = False
            for color in color_combination:
                if color in self.duducos or color in self.current_placement:
                    skip = True
                    break
            if skip:
                continue
            
            # 获取这n种颜色所有未被标记的格子所在的列
            all_cols = set()
            for color in color_combination:
                region = self.regions[color][0]
                for pos in region:
                    r, c = pos
                    if self._is_valid_position(r, c):
                        all_cols.add(c)
            
            # 如果这n种颜色总共恰好占据n列
            if len(all_cols) == n:
                color_names = ", ".join(str(c) for c in color_combination)
                print(f"发现颜色{color_names}总共占据{n}列{all_cols}")
                
                # 将这n列中其他颜色的格子标记为"没有嘟嘟可"
                for c in all_cols:
                    for r in range(self.size):
                        color_at_pos = self.grid[r][c]
                        # 如果这个位置的颜色不在组合中，且未被标记
                        if color_at_pos not in color_combination:
                            pos = (r, c)
                            if pos not in self.no_duduco_positions:
                                self.no_duduco_positions.add(pos)
                                updated = True
                print(f"  - 将这些列中其他颜色的格子标记为'没有嘟嘟可'")
        
        return updated

    def _detect_surrounded_exclusion(self) -> bool:
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
                        print(f"包围排除: ({r},{c})的8邻域覆盖颜色{color}全部{len(unmarked)}个候选格")
                        self.no_duduco_positions.add((r, c))
                        updated = True
                        break
        return updated

    def _detection_loop(self):
        print("\n=== 开始检测循环 ===")
        
        max_iterations = 100
        
        for iteration in range(1, max_iterations + 1):
            changed = False
            
            if self._detect_last_cell():
                changed = True
            for n in range(1, self.size + 1):
                if self._detect_n_color_shared_rows(n):
                    changed = True
            if self._detect_surrounded_exclusion():
                changed = True
            
            print(f"  第{iteration}轮完成，changed={changed}")
            
            if not changed:
                break
        
        if iteration >= max_iterations:
            print(f"!!! 达到最大迭代次数 {max_iterations}，强制退出")
        
        print("=== 检测循环结束 ===\n")

    def _solve_region(self, placed_count: int) -> bool:
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

    def _mini_backtrack_two_colors(self) -> bool:
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
            for pos in common_no:
                if pos not in self.no_duduco_positions:
                    self.no_duduco_positions.add(pos)
                    found = True

        return found

    def solve(self):
        print("开始检测循环...")
        self._detection_loop()
        
        print(f"已发现 {len(self.duducos)} 个嘟嘟可")
        
        self.print_detection_result()
        self.save_detection_result()
        
        print("开始小型回溯...")
        while self._mini_backtrack_two_colors():
            print("mini回溯有新发现，重跑规则循环...")
            self._detection_loop()
            print(f"现在确定: {len(self.duducos)}个嘟嘟可")
            self.print_detection_result()
        
        print(f"进入主回溯，已确定{len(self.duducos)}个，共{len(self.regions)}色")
        self._solve_region(len(self.duducos))
        print(f"主回溯结束，找到{len(self.solutions)}个解")
        return self.solutions

    def print_solution(self, solution: Dict[int, Tuple[int, int]]):
        result_grid = [['  .  ' for _ in range(self.size)] for _ in range(self.size)]

        for color, (r, c) in solution.items():
            result_grid[r][c] = f'*{color}*'

        print("\n解法结果（*表示嘟嘟可位置，数字为颜色）：")
        print("    " + " ".join(f"{i+1:2d}" for i in range(self.size)))
        for i, row in enumerate(result_grid):
            print(f"{i+1:2d}  " + " ".join(row))
        print()
        print("嘟嘟可位置详情：")
        for color, (r, c) in sorted(solution.items(), key=lambda x: x[1][0]):
            print(f"  颜色{color}: ({r+1}, {c+1})")
        print()

    def print_detection_result(self):
        """打印检测结果：X表示没有嘟嘟可的位置，*表示嘟嘟可位置，数字表示原颜色"""
        print("\nDetection Result (*=duduco, X=no duduco, number=color):")
        print("    " + " ".join(str(i) for i in range(self.size)))
        
        for r in range(self.size):
            row_str = f"{r:2d}  "
            for c in range(self.size):
                pos = (r, c)
                if pos in self.duducos.values():
                    row_str += ' *  '
                elif r in self.no_duduco_rows or c in self.no_duduco_cols or pos in self.no_duduco_positions:
                    row_str += ' X  '
                else:
                    color = self.grid[r][c]
                    row_str += f'{color}  '
            print(row_str)
        
        print()

    def save_detection_result(self, filename: str = "detection_result.txt"):
        """将检测结果保存到txt文件中"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("嘟嘟可谜题检测结果\n")
            f.write("=" * 40 + "\n\n")
            f.write("符号说明:\n")
            f.write("  * : 嘟嘟可位置\n")
            f.write("  X : 没有嘟嘟可\n")
            f.write("  数字 : 原始颜色（未被标记）\n\n")
            f.write("检测到的嘟嘟可数量: " + str(len(self.duducos)) + "\n\n")
            
            # 打印嘟嘟可详情
            if self.duducos:
                f.write("嘟嘟可位置详情:\n")
                for color, pos in sorted(self.duducos.items(), key=lambda x: x[1][0]):
                    f.write(f"  颜色{color}: ({pos[0]+1}, {pos[1]+1})\n")
                f.write("\n")
            
            # 打印网格
            f.write("网格状态:\n")
            f.write("    " + " ".join(f"{i:2d}" for i in range(self.size)) + "\n")
            f.write("  +" + "--" * self.size + "\n")
            
            for r in range(self.size):
                row_str = f"{r:2d} |"
                for c in range(self.size):
                    pos = (r, c)
                    if pos in self.duducos.values():
                        row_str += ' * '
                    elif r in self.no_duduco_rows or c in self.no_duduco_cols or pos in self.no_duduco_positions:
                        row_str += ' X '
                    else:
                        color = self.grid[r][c]
                        row_str += f'{color:2d} '
                f.write(row_str + "\n")
        
        print(f"\n检测结果已保存到文件: {filename}")


def parse_input(input_str: str) -> Tuple[List[List[int]], int]:
    lines = input_str.strip().split('\n')
    size = int(lines[0].strip())
    grid = []

    for i in range(1, size + 1):
        row = []
        for num in lines[i].strip().split():
            row.append(int(num))
        grid.append(row)

    colors = set()
    for row in grid:
        colors.update(row)

    return grid, len(colors)


if __name__ == "__main__":
    print("=" * 50)
    print("嘟嘟可谜题求解器")
    print("=" * 50)

    try:
        with open("10.txt", 'r', encoding='utf-8') as f:
            input_str = f.read()
        print("已从 10.txt 读取谜题")
    except FileNotFoundError:
        print("\n输入格式：")
        print("第一行：网格大小 N")
        print("接下来N行：每行N个数字（颜色编号，用空格分隔）")
        print("\n示例：")
        print("3")
        print("1 1 2")
        print("1 2 2")
        print("1 2 3")
        print("\n" + "=" * 50)

        print("\n请输入网格信息（输入一行空行结束）：")

        lines = []
        while True:
            try:
                line = input()
                if line.strip() == "":
                    break
                lines.append(line)
            except EOFError:
                break

        input_str = '\n'.join(lines)

    try:
        grid, num_colors = parse_input(input_str)
        print(f"\n网格大小: {len(grid)}x{len(grid)}")
        print(f"颜色数量: {num_colors}")

        solver = DuducoPuzzleSolver(grid, num_colors)
        print(f"找到 {len(solver.regions)} 个颜色区域")

        print("\n正在求解...")
        # start_time = time.time()  # 计时功能，需要时取消注释
        solutions = solver.solve()
        # end_time = time.time()  # 计时功能，需要时取消注释
        # elapsed_time = end_time - start_time  # 计时功能，需要时取消注释

        if solutions:
            print(f"\n找到 {len(solutions)} 个解！")
            # print(f"求解用时: {elapsed_time:.4f} 秒\n")  # 计时功能，需要时取消注释
            for i, sol in enumerate(solutions[:10], 1):
                print(f"--- 解法 {i} ---")
                solver.print_solution(sol)
                
                # 保存解到文件（覆盖模式）
                with open("solution.txt", 'w', encoding='utf-8') as f:
                    f.write("嘟嘟可谜题解\n")
                    f.write("=" * 40 + "\n\n")
                    f.write("网格状态:\n")
                    f.write("    " + " ".join(f"{c:2d}" for c in range(len(grid))) + "\n")
                    f.write("  +" + "--" * len(grid) + "\n")
                    for r in range(len(grid)):
                        row_str = f"{r:2d} |"
                        for c in range(len(grid)):
                            if (r, c) in sol.values():
                                row_str += ' * '
                            else:
                                row_str += f'{grid[r][c]:2d} '
                        f.write(row_str + "\n")
                    f.write("\n嘟嘟可位置:\n")
                    for color, pos in sorted(sol.items()):
                        f.write(f"  颜色{color}: ({pos[0]}, {pos[1]})\n")
                print("解已保存到文件: solution.txt")
        else:
            print("\n未找到解！")

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
