import difflib
import inspect
import itertools
import linecache
import os
import re
import subprocess
import typing
from collections import defaultdict
from pathlib import Path
from typing import Callable, Generic, Iterator, Literal, Sequence, TypeVar

import py.path

from spy.textbuilder import Color

T = TypeVar("T")


class OrderedSet(Generic[T]):
    """
    A set that maintains insertion order.
    """

    def __init__(self) -> None:
        self._dict: dict[T, None] = {}

    def add(self, item: T) -> None:
        self._dict[item] = None

    def __contains__(self, item: T) -> bool:
        return item in self._dict

    def __iter__(self) -> Iterator[T]:
        return iter(self._dict)


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
def colors_coordinates(ast_module, ast_color_map) -> dict[int, list[tuple[str, str]]]:
    """
    Generate a mapping line_number:col_ranges with associated colors for AST nodes.

    This function walks through all nodes in the given AST module and maps each node
    that has a color specified in `ast_color_map` to its line and column range.
    The result is a dictionary where each key is a line number and each value is a list
    of tuples. Each tuple contains a string representing the column range in the format
    "start:end" and the corresponding color.

    Args:
        ast_module (spy.ast.Module): The AST module to traverse.
        ast_color_map (dict[spy.ast.Node, str]): A mapping from AST nodes to colors.

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
        if ast_color_map.get(node):
            # collect just the lines that needs to be colored
            coords[node.loc.line_start].append((col_range, ast_color_map.get(node)))
    return dict(coords)


def format_colors_as_json(coords_dict: dict[int, list[tuple[str, str]]]) -> str:
    """
    Convert color coordinates to JSON format for editor integration.

    Args:
        coords_dict: Dictionary mapping line numbers to list of (col_range, color) tuples,
                     as returned by colors_coordinates()

    Returns:
        JSON string with format: [{"line": 10, "col": 5, "length": 3, "type": "blue"}, ...]

    Example:
        >>> coords = {3: [("4:9", "red"), ("10:15", "blue")]}
        >>> format_colors_as_json(coords)
        '[{"line": 3, "col": 4, "length": 6, "type": "red"}, ...]'
    """
    import json

    highlights = []
    for line_num, spans in coords_dict.items():
        for col_range, color in spans:
            start_str, end_str = col_range.split(":")
            start = int(start_str)
            end = int(end_str)
            length = end - start + 1

            highlights.append(
                {"line": line_num, "col": start, "length": length, "type": color}
            )

    return json.dumps(highlights, indent=2)


_record_src_counter = itertools.count()


def record_src_in_linecache(source: str, *, name: str = "exec") -> str:
    """
    Register a source string in linecache so that debuggers and tracebacks
    can display its code lines properly.

    Returns a unique pseudo-filename suitable for compile() or exec().
    """
    index = next(_record_src_counter)
    filename = f"<{name}-{index}>"
    linecache.cache[filename] = (
        len(source),
        None,
        [line + "\n" for line in source.splitlines()],
        filename,
    )
    return filename


def cleanup_spyc_files(path: py.path.local, *, verbose: bool = False) -> None:
    """
    Remove all .spyc cache files from __pycache__ directories in the given paths.
    """
    if verbose:
        print(f"Cleaning up {path}:")

    n = 0
    if not path.check(dir=True):
        if verbose:
            print("Not a directory")
        return

    # Use os.walk with onerror handler to gracefully handle permission errors
    def handle_error(error: OSError) -> None:
        if verbose:
            print(f"    Permission denied: {error.filename}")

    for root, dirs, files in os.walk(str(path), onerror=handle_error):
        # Only process __pycache__ directories
        if os.path.basename(root) != "__pycache__":
            continue

        for filename in files:
            if filename.endswith(".spyc"):
                spyc_path = os.path.join(root, filename)
                try:
                    rel_path = os.path.relpath(spyc_path, str(path))
                    if verbose:
                        print(f"    {rel_path}")
                    os.remove(spyc_path)
                    n += 1
                except PermissionError as e:
                    if verbose:
                        print(f"    Permission denied: {rel_path}")

    if verbose:
        if n == 0:
            print("No .spyc files found")
        else:
            print(f"{n} file(s) removed")


if __name__ == "__main__":
    import ast as py_ast

    print_class_hierarchy(py_ast.AST)
