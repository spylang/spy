# -*- encoding: utf-8 -*-
import difflib
import inspect
import re
import subprocess
import typing
from collections import defaultdict
from typing import Callable, Sequence

import py.path

from spy.textbuilder import Color


class AnythingClass:
    """
    Magic object which compares equal to everything. Useful for equality tests
    in which you don't care about the exact value of a specific field.
    """

    def __eq__(self, other: typing.Any) -> bool:
        return True


ANYTHING: typing.Any = AnythingClass()


@typing.no_type_check
def magic_dispatch(self, prefix, obj, *args, **kwargs):
    """
    Dynamically dispatch the execution to a method whose name is computed from
    `prefix` and the class name of `obj`.

    Example:

    class Foo:
        def visit(self, obj):
            return magic_dispatch(self, 'visit', obj)

        def visit_int(self): ...
        def visit_str(self): ...
        def visit_float(self): ...
    """
    methname = f"{prefix}_{obj.__class__.__name__}"
    meth = getattr(self, methname, None)
    if meth is None:
        meth = getattr(self, f"{prefix}_NotImplemented", None)
        if meth is None:
            clsname = self.__class__.__name__
            raise NotImplementedError(f"{clsname}.{methname}")
    return meth(obj, *args, **kwargs)


@typing.no_type_check
def extend(existing_cls):
    """
    Class decorator to extend an existing class with new attributes and
    methods
    """

    def decorator(new_cls):
        for key, value in new_cls.__dict__.items():
            if key.startswith("__"):
                continue
            if hasattr(existing_cls, key):
                clsname = existing_cls.__name__
                raise TypeError(f"class {clsname} has already a member '{key}'")
            setattr(existing_cls, key, value)
        return existing_cls

    return decorator


@typing.no_type_check
def print_class_hierarchy(cls):
    # fmt: off
    CROSS  = "├── "
    BAR    = "│   "
    CORNER = "└── "
    SPACE  = "    "
    # fmt: on
    def print_class(cls, prefix, indent, marker):
        print(f"{prefix}{marker}{cls.__name__}")
        prefix += indent
        subclasses = cls.__subclasses__()
        if subclasses:
            for subcls in subclasses[:-1]:
                print_class(subcls, prefix, indent=BAR, marker=CROSS)
            print_class(subclasses[-1], prefix, indent=SPACE, marker=CORNER)

    print_class(cls, prefix="", indent="", marker="")


def print_diff(a: str, b: str, fromfile: str, tofile: str) -> None:
    la = a.splitlines()
    lb = b.splitlines()
    diff = difflib.unified_diff(la, lb, fromfile, tofile, lineterm="")
    print()
    for line in diff:
        if line.startswith("+"):
            line = Color.set("yellow", line)
        elif line.startswith("-"):
            line = Color.set("red", line)
        elif line.startswith("@@"):
            line = Color.set("fuchsia", line)
        print(line)


def highlight_C_maybe(code: str | bytes) -> str:
    assert isinstance(code, str)
    try:
        import pygments  # type: ignore
    except ImportError:
        return code

    from pygments import highlight
    from pygments.formatters import TerminalFormatter  # type: ignore
    from pygments.lexers import CLexer  # type: ignore

    return highlight(code, CLexer(), TerminalFormatter())


def highlight_spy_maybe(code: str | bytes) -> str:
    assert isinstance(code, str)
    try:
        import pygments  # type: ignore
    except ImportError:
        return code

    from pygments import highlight
    from pygments.formatters import TerminalFormatter  # type: ignore
    from pygments.lexers import CLexer  # type: ignore

    # Regex for ANSI escape sequences
    regexp = re.compile(r"\033\[[0-9;]*m")  # \033 is \x1b

    def has_ansi(text: str) -> bool:
        return bool(regexp.search(text))

    if not has_ansi(code):
        return highlight(code, CLexer(), TerminalFormatter())
    return code


def shortrepr(s: str, n: int) -> str:
    """
    Return a repr of the `s`.

    If len(s) <= n, this is equivalent as repr(s).
    Else, we use '...' to put a cap on the length of s.
    """
    if len(s) > n:
        s = s[: n - 2] + "..."
    return repr(s)


def unbuffer_run(cmdline_s: Sequence[str]) -> subprocess.CompletedProcess:
    """
    Simulate the behavior of the unbuffer command from the expect package.

    Like unbuffer, this assumes the command only outputs to stdout.
    """
    import pexpect

    try:
        cmd = cmdline_s[0]
        args = list(cmdline_s[1:])
        child = pexpect.spawn(command=cmd, args=args)
        child.expect(pexpect.EOF)
        child.wait()  # avoid a race condition on child.exitstatus

        # child.exitstatus is never None if child.wait() finished
        assert child.exitstatus is not None
        returncode = child.exitstatus

        return subprocess.CompletedProcess(
            args=cmdline_s, stdout=child.before, stderr="", returncode=returncode
        )
    except pexpect.exceptions.EOF:
        return subprocess.CompletedProcess(
            args=cmdline_s, stdout=child.before, stderr="", returncode=returncode
        )


def robust_run(
    cmdline: Sequence[str | py.path.local], unbuffer: bool = False
) -> subprocess.CompletedProcess:
    """
    Similar to subprocess.run, but raise an Exception with the content of
    stdout+stderr in case of failure.

    If unbuffer is True, the command is run unbuffered using pexpect.
    """
    cmdline_s = [str(x) for x in cmdline]
    if unbuffer:
        # Note that unbuffer doesn't read from stdin by default
        proc = unbuffer_run(cmdline_s)
    else:
        # Use capture_output=True to capture stdout and stderr separately
        proc = subprocess.run(cmdline_s, capture_output=True)

    if proc.returncode != 0:
        FORCE_COLORS = True
        lines = ["subprocess failed:"]
        lines.append(" ".join(cmdline_s))
        lines.append("")
        errlines = []
        if proc.stdout:
            errlines += proc.stdout.decode("utf-8").splitlines()
        if proc.stderr:
            errlines += proc.stderr.decode("utf-8").splitlines()
        if FORCE_COLORS:
            errlines = [Color.set("default", line) for line in errlines]
        lines += errlines
        msg = "\n".join(lines)
        raise Exception(msg)
    return proc


def func_equals(f: Callable, g: Callable) -> bool:
    """
    Try to determine whether two functions are "the same".

    In particular, they must have same name, same code object and same
    closed-over variables.

    This function is not meant to be perfect, but "good enough". Its main use
    case is to make a sanity check in vm.register_builtin_func, so that we can
    be confident that multiple builtin functions with the same fqn are "the
    same".
    """
    if f is g:
        return True

    if f.__code__ != g.__code__:
        return False

    if f.__defaults__ is not None or g.__defaults__ is not None:
        raise ValueError("unsupported: default arguments")

    if f.__kwdefaults__ is not None or g.__kwdefaults__ is not None:
        raise ValueError("unsupported: kwargs with default arguments")

    # compare closure variables
    cf = inspect.getclosurevars(f)
    cg = inspect.getclosurevars(g)

    # here we use default interp-level comparison for closed-over
    # variables. This should work fine as long as we close over interp-level
    # values. We might need to implement smarter comparison if we want to
    # close over W_* value types (e.g. W_Str('hello')).
    if cf.nonlocals != cg.nonlocals:
        return False

    return True


@typing.no_type_check
def colors_coordinates(ast_module, expr_color_map) -> dict[int, list[tuple[str, str]]]:
    """
    Generate a mapping line_number:col_ranges with associated colors for AST nodes.

    This function walks through all nodes in the given AST module and maps each node
    that has a color specified in `expr_color_map` to its line and column range.
    The result is a dictionary where each key is a line number and each value is a list
    of tuples. Each tuple contains a string representing the column range in the format
    "start:end" and the corresponding color.

    Args:
        ast_module (spy.ast.Module): The AST module to traverse.
        expr_color_map (dict[spy.ast.Node, str]): A mapping from AST nodes to colors.

    Returns:
        dict[int, list[tuple[str, str]]]: A dictionary mapping line numbers to a list of
        (column_range, color) tuples.

    Example:
        >>> colors_coordinates(ast_module, {node: "red", ...})
        {3: [("4:9", "red"), ("10:15", "blue")], 5: [("2:5", "red")]}
    """
    ast_nodes = list(ast_module.walk())
    coords = defaultdict(list)
    for node in ast_nodes:
        col_range = f"{node.loc.col_start}:{node.loc.col_end - 1}"
        if expr_color_map.get(node):
            # collect just the lines that needs to be colored
            coords[node.loc.line_start].append((col_range, expr_color_map.get(node)))
    return dict(coords)


if __name__ == "__main__":
    import ast as py_ast

    print_class_hierarchy(py_ast.AST)
