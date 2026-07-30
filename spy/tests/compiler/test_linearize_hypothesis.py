"""
Hypothesis-based stress test for the linearize pass.

Each example compiles the same SPy source under interp and linearize backends,
then compares return values and stdout. Any discrepancy indicates a bug in the
linearize pass's observational transparency.

To enable stress testing use:
$ pytest --hypothesis-profile=stress -v -s spy/tests/compiler/test_linearize_hypothesis.py

"""

import io
import itertools
import sys
import textwrap
from typing import Any

import py.path
from hypothesis import HealthCheck, given, note, settings
from hypothesis import strategies as st

from spy.backend.interp import InterpModuleWrapper
from spy.vm.vm import SPyVM

PREAMBLE = """
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

@blue
def blue_i32() -> i32:
    return 42
"""

TEMPLATE = """
def foo(x: i32) -> i32:
    y: i32 = 0
    _i: i32 = 0
    {body}
"""


def _run_and_capture(src: str, backend: str, tmpdir: py.path.local) -> tuple[Any, str]:
    vm = SPyVM()
    vm.path.append(str(tmpdir))
    srcfile = tmpdir.join("test.spy")
    srcfile.write(textwrap.dedent(src))
    w_mod = vm.import_("test")
    if backend == "linearize":
        vm.redshift(error_mode="eager")
        vm.linearize_all()
    mod = InterpModuleWrapper(vm, w_mod, backend)
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        result = mod.foo(3)
    finally:
        sys.stdout = old_stdout
    return result, buf.getvalue()


# --- Hypothesis strategies ---


class _NameCounter:
    """Per-example unique name allocator. Reset by creating a new instance."""

    def __init__(self) -> None:
        self._counter = itertools.count()

    def fresh(self) -> str:
        return f"a{next(self._counter)}"


def _make_strategies(counter: _NameCounter) -> tuple[Any, Any, Any, Any]:
    """
    Build (expr_i32, expr_i32_with_block, expr_bool, stmt) strategies sharing
    a single name counter.
    """

    i32_base = st.one_of(
        st.integers(min_value=-5, max_value=5).map(str),
        st.just("x"),
        st.just("N"),
        st.just("read_N()"),
        st.just("f1()"),
        st.just("f2()"),
        st.just("tick()"),
        st.just("blue_i32()"),
    )

    bool_base = st.one_of(
        st.just("True"),
        st.just("False"),
        st.just("side_bool()"),
    )

    # expr_i32 without __block__, used inside block bodies to avoid
    # nested ''' delimiters.
    def extend_i32_no_block(children: st.SearchStrategy[str]) -> st.SearchStrategy[str]:
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

    expr_i32_no_block = st.recursive(i32_base, extend_i32_no_block, max_leaves=20)

    # no-block bool, used inside block bodies
    def extend_bool_no_block(
        bool_children: st.SearchStrategy[str],
    ) -> st.SearchStrategy[str]:
        i32_pair = st.tuples(expr_i32_no_block, expr_i32_no_block)
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

    expr_bool_no_block = st.recursive(bool_base, extend_bool_no_block, max_leaves=10)

    @st.composite
    def make_stmt_no_block(draw: Any) -> str:
        kind = draw(st.integers(min_value=0, max_value=4))
        if kind == 0:
            return f"y = {draw(expr_i32_no_block)}"
        elif kind == 1:
            return f"N = {draw(expr_i32_no_block)}"
        elif kind == 2:
            return draw(st.sampled_from(["tick()", "f1()", "f2()"]))
        elif kind == 3:
            cond = draw(expr_bool_no_block)
            s1 = draw(expr_i32_no_block)
            s2 = draw(expr_i32_no_block)
            return f"if {cond}:\n    y = {s1}\nelse:\n    y = {s2}"
        else:
            cond = draw(expr_bool_no_block)
            body_stmt = draw(st.sampled_from(["tick()", "f1()", "f2()"]))
            return (
                f"_i = 0\nwhile ({cond}) and _i < 3:\n    _i = _i + 1\n    {body_stmt}"
            )

    stmt_no_block = make_stmt_no_block()

    @st.composite
    def block_expr(draw: Any) -> str:
        num_stmts = draw(st.integers(min_value=0, max_value=2))
        stmts = [draw(stmt_no_block) for _ in range(num_stmts)]
        value = draw(expr_i32_no_block)
        body = "\n".join(stmts + [value])
        indented = textwrap.indent(body, "    ")
        return f"__block__('''\n{indented}\n''')"

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

    # expr_i32 extended with __block__: can appear at top level but blocks
    # don't nest (their bodies use expr_i32_no_block to avoid ''' collisions).
    expr_i32_with_block = st.one_of(expr_i32, block_expr())

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

    # statement strategy — AssignLocal, StmtExpr, if
    @st.composite
    def make_stmt(draw: Any) -> str:
        kind = draw(st.integers(min_value=0, max_value=4))
        if kind == 0:
            return f"y = {draw(expr_i32)}"
        elif kind == 1:
            return f"N = {draw(expr_i32)}"
        elif kind == 2:
            # StmtExpr: bare call with side effects
            return draw(st.sampled_from(["tick()", "f1()", "f2()"]))
        elif kind == 3:
            # if <bool>: y = <expr> else: y = <expr>
            cond = draw(expr_bool)
            s1 = draw(expr_i32)
            s2 = draw(expr_i32)
            return f"if {cond}:\n    y = {s1}\nelse:\n    y = {s2}"
        else:
            cond = draw(expr_bool)
            body_stmt = draw(st.sampled_from(["tick()", "f1()", "f2()"]))
            return (
                f"_i = 0\nwhile ({cond}) and _i < 3:\n    _i = _i + 1\n    {body_stmt}"
            )

    stmt = make_stmt()

    return expr_i32, expr_i32_with_block, expr_bool, stmt


@st.composite
def expr_i32_strategy(draw: Any) -> str:
    counter = _NameCounter()
    expr_i32, _, _, _ = _make_strategies(counter)
    return draw(expr_i32)


@st.composite
def expr_i32_with_block_strategy(draw: Any) -> str:
    counter = _NameCounter()
    _, expr_i32_with_block, _, _ = _make_strategies(counter)
    return draw(expr_i32_with_block)


@st.composite
def stmt_program_strategy(draw: Any) -> str:
    counter = _NameCounter()
    expr_i32, _, _, stmt = _make_strategies(counter)
    num_stmts = draw(st.integers(min_value=1, max_value=4))
    stmts = [draw(stmt) for _ in range(num_stmts)]
    ret = draw(expr_i32)
    stmts.append(f"return {ret}")
    body = "\n".join(stmts)
    indented = textwrap.indent(body, "    ")
    # strip the leading indent: TEMPLATE already provides it for the first line
    return indented.lstrip()


class ExampleCounter:
    def __init__(self) -> None:
        self.n = 0

    def next(self) -> int:
        self.log_iteration()
        self.n += 1
        return self.n

    def log_iteration(self) -> None:
        if self.n % 10 == 0:
            sys.stdout.write(str(self.n))
        sys.stdout.write(".")
        sys.stdout.flush()


_example_counter = ExampleCounter()


def test_scaffolding(tmpdir):
    foo_src = TEMPLATE.format(body="return add(f1(), f2())")
    src = PREAMBLE + foo_src
    tmp1 = tmpdir.mkdir("interp")
    tmp2 = tmpdir.mkdir("linearize")
    res_interp, out_interp = _run_and_capture(src, "interp", tmp1)
    res_lin, out_lin = _run_and_capture(src, "linearize", tmp2)
    assert res_interp == res_lin
    assert out_interp == out_lin


@given(expr=expr_i32_strategy())
@settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_single_expr(expr, tmpdir):
    foo_src = TEMPLATE.format(body=f"return {expr}")
    src = PREAMBLE + foo_src
    note(f"Generated source:\n{src}")

    n = _example_counter.next()
    tmp1 = tmpdir.mkdir(f"interp_{n}")
    tmp2 = tmpdir.mkdir(f"linearize_{n}")

    res_interp, out_interp = _run_and_capture(src, "interp", tmp1)
    res_lin, out_lin = _run_and_capture(src, "linearize", tmp2)

    assert res_interp == res_lin, f"return value mismatch on:\n{src}"
    assert out_interp == out_lin, f"stdout mismatch on:\n{src}"


@given(body=stmt_program_strategy())
@settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_many_stmts(body, tmpdir):
    foo_src = TEMPLATE.format(body=body)
    src = PREAMBLE + foo_src
    note(f"Generated source:\n{src}")

    n = _example_counter.next()
    tmp1 = tmpdir.mkdir(f"interp_{n}")
    tmp2 = tmpdir.mkdir(f"linearize_{n}")

    res_interp, out_interp = _run_and_capture(src, "interp", tmp1)
    res_lin, out_lin = _run_and_capture(src, "linearize", tmp2)

    assert res_interp == res_lin, f"return value mismatch on:\n{src}"
    assert out_interp == out_lin, f"stdout mismatch on:\n{src}"


@given(expr=expr_i32_with_block_strategy())
@settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_block_expr(expr, tmpdir):
    foo_src = TEMPLATE.format(body=f"return {expr}")
    src = PREAMBLE + foo_src
    note(f"Generated source:\n{src}")

    n = _example_counter.next()
    tmp1 = tmpdir.mkdir(f"interp_{n}")
    tmp2 = tmpdir.mkdir(f"linearize_{n}")

    res_interp, out_interp = _run_and_capture(src, "interp", tmp1)
    res_lin, out_lin = _run_and_capture(src, "linearize", tmp2)

    assert res_interp == res_lin, f"return value mismatch on:\n{src}"
    assert out_interp == out_lin, f"stdout mismatch on:\n{src}"
