"""
Hypothesis-based stress test for the linearize pass.

Each example compiles the same SPy source under interp and linearize backends,
then compares return values and stdout. Any discrepancy indicates a bug in the
linearize pass's observational transparency.
"""

import itertools
import textwrap
from typing import Any

import py.path
import pytest
from hypothesis import HealthCheck, given, note, settings
from hypothesis import strategies as st

from spy.backend.interp import InterpModuleWrapper
from spy.vm.vm import SPyVM

TEMPLATE = """
var N: i32 = 0

def f1() -> i32:
    print('f1')
    return 10

def f2() -> i32:
    print('f2')
    return 20

def tick() -> i32:
    N = N + 1
    print('tick')
    return N

def read_N() -> i32:
    return N

def side_bool() -> bool:
    print('sb')
    return True

def add(a: i32, b: i32) -> i32:
    return a + b

def sub(a: i32, b: i32) -> i32:
    return a - b

def foo(x: i32) -> i32:
    y: i32 = 0
    return {body_src}
"""


STMT_TEMPLATE = """
var N: i32 = 0

def f1() -> i32:
    print('f1')
    return 10

def f2() -> i32:
    print('f2')
    return 20

def tick() -> i32:
    N = N + 1
    print('tick')
    return N

def read_N() -> i32:
    return N

def side_bool() -> bool:
    print('sb')
    return True

def add(a: i32, b: i32) -> i32:
    return a + b

def sub(a: i32, b: i32) -> i32:
    return a - b

def foo(x: i32) -> i32:
    y: i32 = 0
{foo_body}
"""


def build_program(body_src: str) -> str:
    return TEMPLATE.format(body_src=body_src)


def build_stmt_program(foo_body: str) -> str:
    return STMT_TEMPLATE.format(foo_body=foo_body)


def _run_and_capture(
    src: str, backend: str, tmpdir: py.path.local, capfd: Any
) -> tuple[Any, str]:
    vm = SPyVM()
    vm.path.append(str(tmpdir))
    srcfile = tmpdir.join("test.spy")
    srcfile.write(textwrap.dedent(src))
    w_mod = vm.import_("test")
    if backend == "linearize":
        vm.redshift(error_mode="eager")
        vm.linearize_all()
    mod = InterpModuleWrapper(vm, w_mod, backend)
    capfd.readouterr()  # drain any prior output
    result = mod.foo(3)
    out, _ = capfd.readouterr()
    return result, out


# --- Hypothesis strategies ---


class _NameCounter:
    """Per-example unique name allocator. Reset by creating a new instance."""

    def __init__(self) -> None:
        self._counter = itertools.count()

    def fresh(self) -> str:
        return f"a{next(self._counter)}"


def _make_strategies(counter: _NameCounter) -> tuple[Any, Any, Any]:
    """
    Build (expr_i32, expr_bool, stmt) strategies sharing a single name counter.
    """

    i32_base = st.one_of(
        st.integers(min_value=-5, max_value=5).map(str),
        st.just("x"),
        st.just("N"),
        st.just("read_N()"),
        st.just("f1()"),
        st.just("f2()"),
        st.just("tick()"),
    )

    bool_base = st.one_of(
        st.just("True"),
        st.just("False"),
        st.just("side_bool()"),
    )

    # Build expr_i32 first (no bool dependency), then expr_bool referencing it,
    # then stmt referencing both.

    def extend_i32(children: st.SearchStrategy[str]) -> st.SearchStrategy[str]:
        a_b = st.tuples(children, children)
        walrus_local = children.map(lambda a: f"(y := {a})")
        walrus_cell = children.map(lambda a: f"(N := {a})")
        arithmetic = a_b.flatmap(
            lambda ab: st.one_of(
                st.just(f"({ab[0]} + {ab[1]})"),
                st.just(f"({ab[0]} - {ab[1]})"),
                st.just(f"add({ab[0]}, {ab[1]})"),
                st.just(f"sub({ab[0]}, {ab[1]})"),
            )
        )
        return st.one_of(arithmetic, walrus_local, walrus_cell)

    expr_i32 = st.recursive(i32_base, extend_i32, max_leaves=20)

    def extend_bool(bool_children: st.SearchStrategy[str]) -> st.SearchStrategy[str]:
        i32_pair = st.tuples(expr_i32, expr_i32)
        bool_pair = st.tuples(bool_children, bool_children)
        comparisons = i32_pair.flatmap(
            lambda ab: st.one_of(
                st.just(f"({ab[0]} < {ab[1]})"),
                st.just(f"({ab[0]} == {ab[1]})"),
            )
        )
        short_circuit = bool_pair.flatmap(
            lambda pq: st.one_of(
                st.just(f"({pq[0]} and {pq[1]})"),
                st.just(f"({pq[0]} or {pq[1]})"),
            )
        )
        return st.one_of(comparisons, short_circuit)

    expr_bool = st.recursive(bool_base, extend_bool, max_leaves=10)

    # M5: __block__ as a composite strategy referencing expr_i32 and stmt.
    # stmt is defined after, so we use a mutable ref only for this one direction.
    stmt_ref: list[Any] = [None]

    @st.composite
    def block_expr(draw: Any) -> str:
        num_stmts = draw(st.integers(min_value=0, max_value=2))
        stmts = [draw(stmt_ref[0]) for _ in range(num_stmts)]
        value = draw(expr_i32)
        body = "\n".join(stmts + [value])
        indented = textwrap.indent(body, "    ")
        return f"__block__('''\n{indented}\n''')"

    # M6: statement strategy — AssignLocal, StmtExpr, if
    @st.composite
    def make_stmt(draw: Any) -> str:
        kind = draw(st.integers(min_value=0, max_value=3))
        if kind == 0:
            return f"y = {draw(expr_i32)}"
        elif kind == 1:
            return f"N = {draw(expr_i32)}"
        elif kind == 2:
            # StmtExpr: bare call with side effects
            return draw(st.sampled_from(["tick()", "f1()", "f2()"]))
        else:
            # if <bool>: y = <expr> else: y = <expr>
            cond = draw(expr_bool)
            s1 = draw(expr_i32)
            s2 = draw(expr_i32)
            return f"if {cond}:\n    y = {s1}\nelse:\n    y = {s2}"

    stmt = make_stmt()
    stmt_ref[0] = stmt

    return expr_i32, expr_bool, stmt


# Module-level strategy: build a new counter per draw via @composite
@st.composite
def expr_i32_strategy(draw: Any) -> str:
    counter = _NameCounter()
    expr_i32, _, _ = _make_strategies(counter)
    return draw(expr_i32)


# M6: statement-shape program: a few stmts before the return
@st.composite
def stmt_program_strategy(draw: Any) -> str:
    counter = _NameCounter()
    expr_i32, expr_bool, stmt = _make_strategies(counter)
    num_stmts = draw(st.integers(min_value=1, max_value=4))
    stmts = [draw(stmt) for _ in range(num_stmts)]
    ret = draw(expr_i32)
    # indent every line of each stmt by 4 spaces
    indented = []
    for s in stmts:
        for line in s.splitlines():
            indented.append("    " + line)
    indented.append(f"    return {ret}")
    return "\n".join(indented)


# --- Scaffolding test (M1): hard-coded source, no Hypothesis ---


def test_linearize_scaffolding(tmpdir, capfd):
    src = build_program("add(f1(), f2())")
    tmp1 = tmpdir.mkdir("interp")
    tmp2 = tmpdir.mkdir("linearize")
    res_interp, out_interp = _run_and_capture(src, "interp", tmp1, capfd)
    res_lin, out_lin = _run_and_capture(src, "linearize", tmp2, capfd)
    assert res_interp == res_lin
    assert out_interp == out_lin


# --- Hypothesis test (M2+): random i32 expressions ---


_example_counter = itertools.count()


@given(body=expr_i32_strategy())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_linearize_preserves_semantics(body, tmpdir, capfd):
    src = build_program(body)
    note(f"Generated source:\n{src}")

    n = next(_example_counter)
    tmp1 = tmpdir.mkdir(f"interp_{n}")
    tmp2 = tmpdir.mkdir(f"linearize_{n}")

    res_interp, out_interp = _run_and_capture(src, "interp", tmp1, capfd)
    res_lin, out_lin = _run_and_capture(src, "linearize", tmp2, capfd)

    assert res_interp == res_lin, f"return value mismatch on:\n{src}"
    assert out_interp == out_lin, f"stdout mismatch on:\n{src}"


# --- Hypothesis test (M6): statement-shape programs ---


@given(foo_body=stmt_program_strategy())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_linearize_preserves_semantics_stmts(foo_body, tmpdir, capfd):
    src = build_stmt_program(foo_body)
    note(f"Generated source:\n{src}")

    n = next(_example_counter)
    tmp1 = tmpdir.mkdir(f"interp_{n}")
    tmp2 = tmpdir.mkdir(f"linearize_{n}")

    res_interp, out_interp = _run_and_capture(src, "interp", tmp1, capfd)
    res_lin, out_lin = _run_and_capture(src, "linearize", tmp2, capfd)

    assert res_interp == res_lin, f"return value mismatch on:\n{src}"
    assert out_interp == out_lin, f"stdout mismatch on:\n{src}"
