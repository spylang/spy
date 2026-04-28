import textwrap

import pytest

from spy.backend.spy import FQN_FORMAT, SPyBackend
from spy.fqn import FQN
from spy.tests.support import CompilerTest, with_additional_backends
from spy.util import print_diff
from spy.vm.function import W_ASTFunc


@with_additional_backends(["linearize"])
class TestLinearize(CompilerTest):
    def assert_linearize(
        self, funcname: str, expected: str, *, fqn_format: FQN_FORMAT = "short"
    ) -> None:
        assert self.backend == "linearize"
        fqn = FQN(f"test::{funcname}")
        w_func = self.vm.lookup_global(fqn)
        b = SPyBackend(self.vm, fqn_format=fqn_format)
        b.modname = "test"
        b.dump_w_func(fqn, w_func)
        got = b.out.build().strip()
        expected = textwrap.dedent(expected).strip()
        if got != expected:
            print_diff(expected, got, "expected", "got")
            pytest.fail("assert_linearize failed")

    def test_simple(self):
        src = """
        def foo(x: i32) -> i32:
            return x
        """
        mod = self.compile(src)
        assert mod.foo(42) == 42
        #
        if self.backend == "linearize":
            expected = """
            def foo(x: i32) -> i32:
                return x
            """
            self.assert_linearize("foo", expected)

    def test_call_order(self, capfd):
        # see also the related TestNative.test_call_order.
        #
        # In C, call order is not specified. This test happened to pass "by chance" when
        # compiled to WASM (the default for the C backend), but to fail when compiled to
        # x86_64, which is what we test in TestNative.
        src = """
        def f1() -> i32:
            print('f1')
            return 10

        def f2() -> i32:
            print('f2')
            return 3

        def sub(a: i32, b: i32) -> i32:
            return a - b

        def foo() -> i32:
            return sub(f1(), f2())
        """
        mod = self.compile(src)
        assert mod.foo() == 7
        if self.backend == "C":
            mod.ll.call("spy_flush")
        out, err = capfd.readouterr()
        assert out.splitlines() == ["f1", "f2"]
        #
        if self.backend == "linearize":
            expected = """
            def foo() -> i32:
                $v0: i32 = `test::f1`()
                $v1: i32 = `test::f2`()
                return `test::sub`($v0, $v1)
            """
            self.assert_linearize("foo", expected)

    def test_dont_spill_pure_calls(self):
        src = """
        def add(x: i32, y: i32) -> i32:
            return x + y

        def foo(x: i32) -> i32:
            return add(x + 1, x + 2)
        """
        mod = self.compile(src)
        assert mod.foo(10) == 23
        #
        if self.backend == "linearize":
            expected = """
            def foo(x: i32) -> i32:
                return `test::add`(x + 1, x + 2)
            """
            self.assert_linearize("foo", expected)

    def test_spill_names_before_call(self, capfd):
        # in this test "a" is spilled because of the later g(), while "c" and "d" don't
        # need spilling
        src = """
        def g() -> i32:
            print('g')
            return 100

        def bar(a: i32, b: i32, c: i32, d: i32) -> i32:
            print('bar')
            return a + b + c + d

        def foo(a: i32, c: i32, d: i32) -> i32:
            return bar(a, 1 + g(), c, d)
        """
        mod = self.compile(src)
        assert mod.foo(1, 3, 4) == 1 + 101 + 3 + 4
        if self.backend == "C":
            mod.ll.call("spy_flush")
        out, err = capfd.readouterr()
        assert out.splitlines() == ["g", "bar"]
        #
        if self.backend == "linearize":
            expected = """
            def foo(a: i32, c: i32, d: i32) -> i32:
                $v0: i32 = a
                $v1: i32 = `test::g`()
                return `test::bar`($v0, 1 + $v1, c, d)
            """
            self.assert_linearize("foo", expected)

    def test_dont_spill_name_variants(self):
        # exercise the various ast.Name* variants which survive after
        # redshift: NameLocalDirect (plain param), NameOuterDirect (module
        # const), NameOuterCell (module var).
        src = """
        K: i32 = 100
        var V: i32 = 200

        def foo4(a: i32, b: i32, c: i32, d: i32) -> i32:
            return a + b + c + d

        def foo(a: i32) -> i32:
            return foo4(a, K, V, a)
        """
        mod = self.compile(src)
        assert mod.foo(1) == 1 + 100 + 200 + 1
        #
        if self.backend == "linearize":
            expected = """
            def foo(a: i32) -> i32:
                return `test::foo4`(a, 100, `test::V`, a)
            """
            self.assert_linearize("foo", expected)

    def test_if(self):
        src = """
        def g() -> i32:
            return 42

        def foo(x: bool) -> i32:
            if x:
                return g()
            else:
                return 0
        """
        mod = self.compile(src)
        assert mod.foo(True) == 42
        assert mod.foo(False) == 0
        #
        if self.backend == "linearize":
            expected = """
            def foo(x: bool) -> i32:
                if x:
                    return `test::g`()
                else:
                    return 0
            """
            self.assert_linearize("foo", expected)

    def test_assign_local(self):
        src = """
        def g() -> i32:
            return 1

        def foo() -> i32:
            x: i32 = 0
            x = g()
            return x
        """
        mod = self.compile(src)
        assert mod.foo() == 1
        #
        if self.backend == "linearize":
            expected = """
            def foo() -> i32:
                x: i32 = 0
                x = `test::g`()
                return x
            """
            self.assert_linearize("foo", expected)

    def test_and(self, capfd):
        # `and` is short-circuit: if the RHS contains stmts which must be hoisted
        # (e.g. a BlockExpr body), hoisting them unconditionally would break
        # short-circuit.  In that case we must lower the And to an explicit if/else, so
        # that the hoisted stmts only run on the short-circuit path.
        src = """
        def side_effect() -> bool:
            print('rhs')
            return True

        # this is rewritten into an 'If' because __block__ triggers hoisted stmts
        def f1(x: bool) -> bool:
            return x and __block__('''
                y: bool = side_effect()
                y
            ''')

        # this is kept as 'And' because we don't need to hoist anything
        def f2(x: bool) -> bool:
            return x and side_effect()
        """
        mod = self.compile(src)
        assert mod.f1(False) == False
        assert mod.f2(False) == False
        if self.backend == "C":
            mod.ll.call("spy_flush")
        out, err = capfd.readouterr()
        assert out == ""
        #
        if self.backend == "linearize":
            expected_f1 = """
            def f1(x: bool) -> bool:
                if x:
                    y: bool = `test::side_effect`()
                    $v0: bool = y
                else:
                    $v0 = x
                return $v0
            """
            self.assert_linearize("f1", expected_f1)
            expected_f2 = """
            def f2(x: bool) -> bool:
                return x and `test::side_effect`()
            """
            self.assert_linearize("f2", expected_f2)

    def test_or(self, capfd):
        # `or` is short-circuit: see also test_and
        src = """
        def side_effect() -> bool:
            print('rhs')
            return False

        def foo(x: bool) -> bool:
            return x or __block__('''
                y: bool = side_effect()
                y
            ''')
        """
        mod = self.compile(src)
        assert mod.foo(True) == True
        if self.backend == "C":
            mod.ll.call("spy_flush")
        out, err = capfd.readouterr()
        assert out == ""
        #
        if self.backend == "linearize":
            expected = """
            def foo(x: bool) -> bool:
                if x:
                    $v0: bool = x
                else:
                    y: bool = `test::side_effect`()
                    $v0 = y
                return $v0
            """
            self.assert_linearize("foo", expected)

    def test_while_simple(self):
        # when the `while` test has no hoisted stmts, it's a plain passthrough
        src = """
        def foo(n: i32) -> i32:
            i: i32 = 0
            while i < n:
                i = i + 1
            return i
        """
        mod = self.compile(src)
        assert mod.foo(5) == 5
        #
        if self.backend == "linearize":
            expected = """
            def foo(n: i32) -> i32:
                i: i32 = 0
                while i < n:
                    i = i + 1
                return i
            """
            self.assert_linearize("foo", expected)

    def test_while_with_hoists(self, capfd):
        # when the `while` test has hoisted stmts (e.g. an impure call that
        # gets spilled), those hoisted stmts must re-run on every iteration.
        # We lower to:
        #     while True:
        #         <hoisted>
        #         if <test>:
        #             <body>
        #         else:
        #             break
        src = """
        var N: i32 = 0

        def tick() -> i32:
            N = N + 1
            return N

        def foo() -> i32:
            while tick() < 3:
                print(N)
            return N
        """
        mod = self.compile(src)
        assert mod.foo() == 3
        if self.backend == "C":
            mod.ll.call("spy_flush")
        out, err = capfd.readouterr()
        # tick() returns 1, 2, 3; body runs with N=1 and N=2.
        assert out.splitlines() == ["1", "2"]
        #
        if self.backend == "linearize":
            expected = """
            def foo() -> i32:
                while True:
                    $v0: i32 = `test::tick`()
                    if `operator::bool_not`($v0 < 3):
                        break
                    print_i32(`test::N`)
                return `test::N`
            """
            self.assert_linearize("foo", expected)

    def test_assignexpr_local(self):
        # AssignExprLocal is side-effecting: it must be spilled, and Names
        # seen before it must be spilled too so they capture the PRE-assignment
        # value. The Name use AFTER must see the POST-assignment value, so it
        # stays un-spilled and reads the (now updated) local.
        src = """
        def g() -> i32:
            return 7

        def foo3(a: i32, b: i32, c: i32) -> i32:
            return a * 100 + b * 10 + c

        def foo(x: i32) -> i32:
            return foo3(x, (x := g()), x)
        """
        mod = self.compile(src)
        assert mod.foo(5) == 577
        #
        if self.backend == "linearize":
            expected = """
            def foo(x: i32) -> i32:
                $v0: i32 = x
                $v1: i32 = `test::g`()
                $v2: i32 = x := $v1
                return `test::foo3`($v0, $v2, x)
            """
            self.assert_linearize("foo", expected)

    def test_assignexpr_cell(self):
        src = """
        var V: i32 = 5

        def g() -> i32:
            return 7

        def foo3(a: i32, b: i32, c: i32) -> i32:
            return a * 100 + b * 10 + c

        def foo() -> i32:
            return foo3(V, (V := g()), V)
        """
        mod = self.compile(src)
        assert mod.foo() == 577
        #
        if self.backend == "linearize":
            expected = """
            def foo() -> i32:
                $v0: i32 = `test::V`
                $v1: i32 = `test::g`()
                $v2: i32 = `test::V` := $v1
                return `test::foo3`($v0, $v2, `test::V`)
            """
            self.assert_linearize("foo", expected)

    def test_blockexpr_simple(self):
        src = """
        def foo(a: i32) -> i32:
            return __block__('''
                x: i32 = a
                x
            ''')
        """
        mod = self.compile(src)
        assert mod.foo(7) == 7
        #
        if self.backend == "linearize":
            expected = """
            def foo(a: i32) -> i32:
                x: i32 = a
                return x
            """
            self.assert_linearize("foo", expected)

    def test_blockexpr_single_value(self):
        mod = self.compile("""
        def foo(a: i32) -> i32:
            return __block__('''
                a
            ''')
        """)
        assert mod.foo(42) == 42
        #
        if self.backend == "linearize":
            expected = """
            def foo(a: i32) -> i32:
                return a
            """
            self.assert_linearize("foo", expected)

    def test_blockepxr_multiple_stmts(self):
        mod = self.compile("""
        def foo(a: i32, b: i32) -> i32:
            return __block__('''
                x: i32 = a
                y: i32 = b
                x + y
            ''')
        """)
        assert mod.foo(1, 2) == 3
        #
        if self.backend == "linearize":
            expected = """
            def foo(a: i32, b: i32) -> i32:
                x: i32 = a
                y: i32 = b
                return x + y
            """
            self.assert_linearize("foo", expected)

    def test_blockexpr_in_call_args(self):
        mod = self.compile("""
        def add(a: i32, b: i32) -> i32:
            return a + b

        def f() -> i32:
            return 10

        def g() -> i32:
            return 20

        def foo() -> i32:
            return add(
                __block__('''
                    a: i32 = f()
                    a
                '''),
                __block__('''
                    b: i32 = g()
                    b
                '''),
            )
        """)
        assert mod.foo() == 30
        #
        if self.backend == "linearize":
            expected = """
            def foo() -> i32:
                a: i32 = `test::f`()
                $v0: i32 = a
                b: i32 = `test::g`()
                $v1: i32 = b
                return `test::add`($v0, $v1)
            """
            self.assert_linearize("foo", expected)

    def test_blockexpr_in_binop(self):
        mod = self.compile("""
        def foo(a: i32, b: i32) -> i32:
            return a + __block__('''
                x: i32 = b
                x + 3
            ''')
        """)
        assert mod.foo(2, 5) == 10
        #
        if self.backend == "linearize":
            expected = """
            def foo(a: i32, b: i32) -> i32:
                $v0: i32 = a
                x: i32 = b
                $v1: i32 = x + 3
                return $v0 + $v1
            """
            self.assert_linearize("foo", expected)

    ## def test_spill_implicit_conversion(self):
    ##     # when doppler inserts an implicit conversion call (e.g. the
    ##     # gc_ref->value deref), the resulting Call must carry a w_T so that
    ##     # linearize can spill it to a temp if needed.
    ##     src = """
    ##     from unsafe import gc_alloc, gc_ptr

    ##     @struct
    ##     class Point:
    ##         x: i32
    ##         y: i32

    ##     def idx(x: i32) -> i32:
    ##         return x

    ##     def foo() -> Point:
    ##         p: gc_ptr[Point] = gc_alloc[Point](2)
    ##         p[0] = Point(10, 20)
    ##         p[1] = Point(30, 40)

    ##         # complicated way to do p[0] = p[1] but:
    ##         #   1. idx(1) must be spilled
    ##         #   2. there is an implicit conversion between gc_ref[Point] and Point
    ##         p[idx(0)] = p[idx(1)]
    ##         return p[0]
    ##     """
    ##     mod = self.compile(src)
    ##     p = mod.foo()
    ##     assert p == (30, 40)
