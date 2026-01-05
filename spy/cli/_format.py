from pathlib import Path

from spy.backend.spy import FQN_FORMAT, SPyBackend
from spy.highlight import highlight_src
from spy.vm.function import W_ASTFunc
from spy.vm.vm import SPyVM


def dump_spy_mod(vm: SPyVM, modname: str, full_fqn: bool) -> None:
    fqn_format: FQN_FORMAT = "full" if full_fqn else "short"
    b = SPyBackend(vm, fqn_format=fqn_format)
    spy_code = b.dump_mod(modname)
    print(highlight_src("spy", spy_code))


def dump_spy_mod_ast(vm: SPyVM, modname: str) -> None:
    for fqn, w_obj in vm.fqns_by_modname(modname):
        if isinstance(w_obj, W_ASTFunc) and w_obj.color == "red" and w_obj.fqn == fqn:
            print(f"`{fqn}` = ", end="")
            w_obj.funcdef.pp()
            print()


def colorize_sourcecode(sourcefile: Path, coords_dict: dict) -> str:
    reset = "\033[0m"
    ansi_colors = {"red": "\033[41m\033[30m", "blue": "\033[44m\033[30m"}
    with open(sourcefile) as f:
        lines = f.readlines()

    highlighted_lines = []

    for i, line in enumerate(lines, start=1):
        if i not in coords_dict:
            highlighted_lines.append(line)
            continue

        # Segments in input order: later spans overwrite earlier ones
        spans = [
            (int(s.split(":")[0]), int(s.split(":")[1]), color)
            for s, color in coords_dict[i]
        ]

        # Track color per character using segments
        line_len = len(line)
        color_map = [None] * line_len
        for start, end, color in spans:
            for j in range(start, min(end + 1, line_len)):
                color_map[j] = color

        # Build line from contiguous segments
        result = []
        current_color = None
        cursor = 0
        while cursor < line_len:
            c = color_map[cursor]
            if c != current_color:
                if current_color is not None:
                    result.append(reset)
                if c is not None:
                    # Find contiguous run of this color
                    run_end = cursor
                    while run_end < line_len and color_map[run_end] == c:
                        run_end += 1
                    result.append(ansi_colors[c] + line[cursor:run_end] + reset)
                    cursor = run_end
                    current_color = None
                    continue
                current_color = c
            else:
                result.append(line[cursor])
            cursor += 1

        highlighted_lines.append("".join(result))
    return "".join(
        highlight_src("spy", line.rstrip("\n")) + "\n" for line in highlighted_lines
    )
