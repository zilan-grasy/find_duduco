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
        self.duducos = {}  # 嘟嘟可位置
        self.no_duduco_rows = set()  # 没有嘟嘟可的行
        self.no_duduco_cols = set()  # 没有嘟嘟可的列
        self.no_duduco_positions = set()  # 没有嘟嘟可的位置（周围8格）
        self.detected_colors = set()  # 已检测过的颜色
    
    def _is_valid_position(self, r: int, c: int) -> bool:
        """检查位置(r, c)是否可以放置嘟嘟可"""
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

    def _detect_single_cell(self) -> bool:
        """检测只有一个格子的颜色区域，这些位置一定是嘟嘟可"""
        for color, regions_list in self.regions.items():
            if color in self.duducos or color in self.current_placement:
                continue
                
            region = regions_list[0]
            if len(region) == 1:
                pos = region[0]
                r, c = pos
                # 检查是否有效（未被标记为"没有嘟嘟可"）
                if self._is_valid_position(r, c):
                    self._mark_placement(color, pos)
                    return True
        return False

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

    def _detect_two_cell_patterns(self) -> bool:
        """检测颜色区域中只剩2个未标记格子的情况，根据形状标记相应位置"""
        updated = False
        
        for color, regions_list in self.regions.items():
            if color in self.duducos or color in self.current_placement:
                continue
            
            # 每种颜色在单次大循环中只检查一次
            if color in self.detected_colors:
                continue
            
            region = regions_list[0]
            
            # 获取未被标记为"没有嘟嘟可"的格子
            unmarked = []
            for pos in region:
                r, c = pos
                if self._is_valid_position(r, c):
                    unmarked.append(pos)
            
            # 如果只剩2个未标记的格子
            if len(unmarked) == 2:
                print(f"发现颜色{color}只剩2个未标记格子：{unmarked}")
                
                (r1, c1), (r2, c2) = unmarked
                
                # 情况1：横向（同一行）
                if r1 == r2:
                    row = r1
                    col1, col2 = sorted([c1, c2])
                    print(f"  - 横向，标记两个格子的上下位置")
                    # 标记两个格子的上方为"没有嘟嘟可"
                    if row > 0:
                        self.no_duduco_positions.add((row - 1, col1))
                        self.no_duduco_positions.add((row - 1, col2))
                    # 标记两个格子的下方为"没有嘟嘟可"
                    if row < self.size - 1:
                        self.no_duduco_positions.add((row + 1, col1))
                        self.no_duduco_positions.add((row + 1, col2))
                    updated = True
                
                # 情况2：竖向（同一列）
                elif c1 == c2:
                    col = c1
                    row1, row2 = sorted([r1, r2])
                    print(f"  - 竖向，标记两个格子的左右位置")
                    # 标记两个格子的左边为"没有嘟嘟可"
                    if col > 0:
                        self.no_duduco_positions.add((row1, col - 1))
                        self.no_duduco_positions.add((row2, col - 1))
                    # 标记两个格子的右边为"没有嘟嘟可"
                    if col < self.size - 1:
                        self.no_duduco_positions.add((row1, col + 1))
                        self.no_duduco_positions.add((row2, col + 1))
                    updated = True
            
            # 标记该颜色已检测
            self.detected_colors.add(color)
        
        return updated

    def _detect_three_cell_patterns(self) -> bool:
        """检测颜色区域中只剩3个未标记格子的情况，根据形状标记相应位置"""
        updated = False
        
        for color, regions_list in self.regions.items():
            if color in self.duducos or color in self.current_placement:
                continue
            
            # 每种颜色在单次大循环中只检查一次
            if color in self.detected_colors:
                continue
            
            region = regions_list[0]
            
            # 获取未被标记为"没有嘟嘟可"的格子
            unmarked = []
            for pos in region:
                r, c = pos
                if self._is_valid_position(r, c):
                    unmarked.append(pos)
            
            # 如果只剩3个未标记的格子
            if len(unmarked) == 3:
                print(f"发现颜色{color}只剩3个未标记格子：{unmarked}")
                
                rows = [pos[0] for pos in unmarked]
                cols = [pos[1] for pos in unmarked]
                
                # 情况1：横线（所有在同一行，列连续）
                if len(set(rows)) == 1:
                    row = rows[0]
                    sorted_cols = sorted(cols)
                    if sorted_cols[2] - sorted_cols[0] == 2:
                        mid_col = sorted_cols[1]
                        # 标记中间格子的上下格子为"没有嘟嘟可"
                        if row > 0 and (row - 1, mid_col) not in self.no_duduco_positions:
                            self.no_duduco_positions.add((row - 1, mid_col))
                        if row < self.size - 1 and (row + 1, mid_col) not in self.no_duduco_positions:
                            self.no_duduco_positions.add((row + 1, mid_col))
                        print(f"  - 横线形状，标记中间格子({row},{mid_col})的上下位置")
                        updated = True
                
                # 情况2：竖线（所有在同一列，行连续）
                elif len(set(cols)) == 1:
                    col = cols[0]
                    sorted_rows = sorted(rows)
                    if sorted_rows[2] - sorted_rows[0] == 2:
                        mid_row = sorted_rows[1]
                        # 标记中间格子的左右格子为"没有嘟嘟可"
                        if col > 0 and (mid_row, col - 1) not in self.no_duduco_positions:
                            self.no_duduco_positions.add((mid_row, col - 1))
                        if col < self.size - 1 and (mid_row, col + 1) not in self.no_duduco_positions:
                            self.no_duduco_positions.add((mid_row, col + 1))
                        print(f"  - 竖线形状，标记中间格子({mid_row},{col})的左右位置")
                        updated = True
                
                # 情况3：L型
                else:
                    for pos in unmarked:
                        r, c = pos
                        has_above = (r - 1, c) in unmarked
                        has_below = (r + 1, c) in unmarked
                        has_left = (r, c - 1) in unmarked
                        has_right = (r, c + 1) in unmarked
                        
                        if (has_above + has_below + has_left + has_right) == 2:
                            if has_above and has_left and not has_below and not has_right:
                                if r + 1 < self.size and c + 1 < self.size and (r + 1, c + 1) not in self.no_duduco_positions:
                                    self.no_duduco_positions.add((r + 1, c + 1))
                                    print(f"  - L型，标记被包围的格子({r + 1},{c + 1})")
                                    updated = True
                            elif has_above and has_right and not has_below and not has_left:
                                if r + 1 < self.size and c - 1 >= 0 and (r + 1, c - 1) not in self.no_duduco_positions:
                                    self.no_duduco_positions.add((r + 1, c - 1))
                                    print(f"  - L型，标记被包围的格子({r + 1},{c - 1})")
                                    updated = True
                            elif has_below and has_left and not has_above and not has_right:
                                if r - 1 >= 0 and c + 1 < self.size and (r - 1, c + 1) not in self.no_duduco_positions:
                                    self.no_duduco_positions.add((r - 1, c + 1))
                                    print(f"  - L型，标记被包围的格子({r - 1},{c + 1})")
                                    updated = True
                            elif has_below and has_right and not has_above and not has_left:
                                if r - 1 >= 0 and c - 1 >= 0 and (r - 1, c - 1) not in self.no_duduco_positions:
                                    self.no_duduco_positions.add((r - 1, c - 1))
                                    print(f"  - L型，标记被包围的格子({r - 1},{c - 1})")
                                    updated = True
                            break
            
            # 标记该颜色已检测
            self.detected_colors.add(color)
        
        return updated

    def _detection_loop(self):
        """大循环：依次执行所有检测方法，直到没有新发现"""
        print("\n=== 开始检测循环 ===")
        
        max_iterations = 100
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            changed = False
            
            # 重置已检测颜色集合（用于2格和3格模式检测）
            self.detected_colors.clear()
            
            # 检测方法1-N：n种颜色共享n行/列检测（n从1到网格大小）
            for n in range(1, self.size + 1):
                if self._detect_n_color_shared_rows(n):
                    changed = True
            
            # 检测方法10：3格模式
            if self._detect_three_cell_patterns():
                changed = True
            
            # 检测方法11：2格模式
            if self._detect_two_cell_patterns():
                changed = True
            
            # 检测方法12：行列最后一格检测
            if self._detect_last_cell():
                changed = True
            
            # 检测方法13：单格颜色区域
            if self._detect_single_cell():
                changed = True
            
            print(f"  第{iteration}轮完成，changed={changed}")
            
            # 如果没有任何变化，退出循环
            if not changed:
                break
        
        if iteration >= max_iterations:
            print(f"!!! 达到最大迭代次数 {max_iterations}，强制退出")
        
        print("=== 检测循环结束 ===\n")

    def _is_valid_placement(self, color: int, pos: Tuple[int, int]) -> bool:
        r, c = pos

        if r in self.no_duduco_rows:
            return False
        
        if c in self.no_duduco_cols:
            return False
        
        if pos in self.no_duduco_positions:
            return False
        
        return True

    def _solve_region(self, placed_count: int) -> bool:
        if placed_count >= len(self.regions):
            solution = {**self.duducos, **self.current_placement}
            self.solutions.append(solution)
            return True

        for color in sorted(self.regions.keys()):
            if color in self.duducos or color in self.current_placement:
                continue
                
            region = self.regions[color][0]
            
            valid_positions = []
            for pos in region:
                r, c = pos
                if r in self.no_duduco_rows:
                    continue
                if c in self.no_duduco_cols:
                    continue
                if pos in self.no_duduco_positions:
                    continue
                valid_positions.append(pos)
            
            if not valid_positions:
                return False
            
            for pos in valid_positions:
                self.current_placement[color] = pos
                r, c = pos
                
                # 临时标记为"没有嘟嘟可"
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
                
                # 恢复标记
                self.no_duduco_rows = old_no_duduco_rows
                self.no_duduco_cols = old_no_duduco_cols
                self.no_duduco_positions = old_no_duduco_positions
                del self.current_placement[color]
        
        return False

    def solve(self):
        # 执行检测大循环
        self._detection_loop()
        
        print(f"已发现 {len(self.duducos)} 个嘟嘟可")
        
        # 打印检测结果
        self.print_detection_result()
        
        # 保存检测结果到文件
        self.save_detection_result()
        
        # 开始回溯求解
        self._solve_region(len(self.duducos))
        return self.solutions

    def print_solution(self, solution: Dict[int, Tuple[int, int]]):
        result_grid = [['  .  ' for _ in range(self.size)] for _ in range(self.size)]

        for color, (r, c) in solution.items():
            result_grid[r][c] = f'*{color}*'

        print("\n解法结果（*表示嘟嘟可位置，数字为颜色）：")
        print("  " + " ".join(str(i) for i in range(self.size)))
        for i, row in enumerate(result_grid):
            print(f"{i} " + " ".join(row))
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
                for color, pos in sorted(self.duducos.items()):
                    f.write(f"  颜色{color}: ({pos[0]}, {pos[1]})\n")
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
