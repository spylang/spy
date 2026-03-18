from pathlib import Path

import spy.ast
from spy.analyze.symtable import Color
from spy.backend.html import HTMLBackend, SpyastJs
from spy.backend.spy import FQN_FORMAT, SPyBackend
from spy.highlight import highlight_src
from spy.util import build_char_color_map
from spy.vm.function import W_ASTFunc
from spy.vm.vm import SPyVM


def dump_spy_mod(vm: SPyVM, modname: str, full_fqn: bool) -> None:
    fqn_format: FQN_FORMAT = "full" if full_fqn else "short"
    b = SPyBackend(vm, fqn_format=fqn_format)
    spy_code = b.dump_mod(modname).rstrip()
    print(highlight_src("spy", spy_code))


def dump_spy_mod_ast(vm: SPyVM, modname: str) -> None:
    for fqn, w_obj in vm.fqns_by_modname(modname):
        if isinstance(w_obj, W_ASTFunc) and w_obj.color == "red" and w_obj.fqn == fqn:
            print(f"`{fqn}` = ", end="")
            w_obj.funcdef.pp()
            print()


def dump_spy_mod_html(vm: SPyVM, modname: str, spyast_js: SpyastJs) -> str:
    """
    Build an HTML page visualizing all red W_ASTFuncs in the given module.
    Returns the HTML string.
    """
    sections = []
    for fqn, w_obj in vm.fqns_by_modname(modname):
        if isinstance(w_obj, W_ASTFunc) and w_obj.color == "red" and w_obj.fqn == fqn:
            sections.append((str(fqn), w_obj.funcdef))
    b = HTMLBackend(
        spyast_js, vm=vm, is_redshifted=True, ast_color_map=vm.ast_color_map
    )
    return b.generate(sections)


def dump_colorize_html(
    orig_mod: spy.ast.Module,
    ast_color_map: dict[spy.ast.Node, Color],
    spyast_js: SpyastJs,
) -> str:
    modname = orig_mod.filename
    b = HTMLBackend(spyast_js, ast_color_map=ast_color_map, start_all_collapsed=True)
    return b.generate([(modname, orig_mod)])


def colorize_sourcecode(sourcefile: Path, coords_dict: dict) -> str:
    reset = "\033[0m"
    ansi_colors = {
        "red": "\033[48;5;174m\033[30m",  # 256-color: light pink
        "blue": "\033[48;5;110m\033[30m",  # 256-color: light steel blue
    }
    with open(sourcefile) as f:
        lines = f.readlines()

    highlighted_lines = []

    for i, line in enumerate(lines, start=1):
        if i not in coords_dict:
            highlighted_lines.append(line)
            continue

        # coords_dict uses inclusive end (col_end - 1); convert to exclusive
        spans = [
            (int(s.split(":")[0]), int(s.split(":")[1]) + 1, color)
            for s, color in coords_dict[i]
        ]
        color_map = build_char_color_map(line, spans)

        # Render ANSI escape sequences from the color map
        result = []
        cursor = 0
        while cursor < len(line):
            c = color_map[cursor]
            if c is not None:
                run_end = cursor + 1
                while run_end < len(line) and color_map[run_end] == c:
                    run_end += 1
                result.append(ansi_colors[c] + line[cursor:run_end] + reset)
                cursor = run_end
            else:
                result.append(line[cursor])
                cursor += 1

        highlighted_lines.append("".join(result))
    return "".join(highlighted_lines)
