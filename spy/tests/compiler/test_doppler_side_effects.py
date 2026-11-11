from spy.tests.support import CompilerTest, no_C
from spy.vm.b import B


class TestDopplerSideEffects(CompilerTest):
    @no_C
    def test_STATIC_TYPE_side_effects(self):
        src = """
        var x: i32 = 0

        def get_x() -> i32:
            return x

        def inc() -> i32:
            global x
            x = x + 1
            return x

        def foo() -> type:
            return STATIC_TYPE(inc())
        """
        mod = self.compile(src)
        assert mod.get_x() == 0
        w_T = mod.foo(unwrap=False)
        assert w_T is B.w_i32
        assert mod.get_x() == 1

    def test_MetaArg_eval_order_red_result(self):
        src = """
        from operator import OpSpec

        var log: i32 = 0

        def reset() -> None:
            global log
            log = 0

        def get_log() -> i32:
            return log

        def step(k: i32) -> i32:
            global log
            log = log * 10 + k
            return k

        # ------------
        @blue.metafunc
        def drop_all_args(m_a):
            def impl() -> i32:
                return 42
            return OpSpec(impl, []) # NOTE: here we ignore m_a

        def call_drop_all_args() -> i32:
            return drop_all_args(step(1))

        # ------------
        @blue.metafunc
        def drop_middle_arg(m_a, m_b, m_c):
            def impl(a: i32, c: i32) -> i32:
                return a * 10 + c
            return OpSpec(impl, [m_a, m_c]) # NOTE: here we ignore m_b

        def call_drop_middle_arg() -> i32:
            return drop_middle_arg(step(1), step(2), step(3))

        #-------------
        @blue.metafunc
        def drop_trailing_arg(m_a, m_b):
            def impl(a: i32) -> i32:
                return a
            return OpSpec(impl, [m_a]) # NOTE: here we ignore m_b

        def call_drop_trailing_arg() -> i32:
            return drop_trailing_arg(step(1), step(2))

        #-------------
        @blue.metafunc
        def reorder_args(m_a, m_b):
            def impl(b: i32, a: i32) -> i32:
                return b * 10 + a
            return OpSpec(impl, [m_b, m_a]) # NOTE: here we swap the args

        def call_reorder_args() -> i32:
            return reorder_args(step(1), step(2))

        #-------------
        @blue.metafunc
        def duplicate_args(m_a):
            def impl(a1: i32, a2: i32) -> i32:
                return a1 * 10 + a2
            return OpSpec(impl, [m_a, m_a]) # NOTE: here we pass m_a twice

        def call_duplicate_args() -> i32:
            return duplicate_args(step(1))

        """
        mod = self.compile(src)
        assert mod.call_drop_all_args() == 42
        assert mod.get_log() == 1

        mod.reset()
        assert mod.call_drop_middle_arg() == 13
        assert mod.get_log() == 123

        mod.reset()
        assert mod.call_drop_trailing_arg() == 1
        assert mod.get_log() == 12

        mod.reset()
        assert mod.call_reorder_args() == 21
        assert mod.get_log() == 12

        mod.reset()
        assert mod.call_duplicate_args() == 11
        assert mod.get_log() == 1

    def test_MetaArg_eval_order_blue_result(self):
        src = """
        from operator import OpSpec
        from __spy__ import COLOR

        var log: i32 = 0

        def reset() -> None:
            global log
            log = 0

        def get_log() -> i32:
            return log

        def step(k: i32) -> i32:
            global log
            log = log * 10 + k
            return k

        # ------------
        @blue.metafunc
        def drop_all_args(m_a, m_b, m_c):
            @blue
            def impl() -> i32:
                return 42
            return OpSpec(impl, []) # NOTE: here we ignore all the args

        def call_drop_all_args() -> i32:
            return drop_all_args(step(1), step(2), step(3))

        # ------------
        @blue.metafunc
        def const_result(m_a, m_b):
            return OpSpec.const(42)

        def call_const_result() -> i32:
            return const_result(step(1), step(2))

        # ------------
        @blue.metafunc
        def use_blue_arg(m_a, m_b):
            @blue
            def impl(b: i32) -> i32:
                return b
            return OpSpec(impl, [m_b]) # NOTE: m_a is red and ignored, m_b is blue

        def call_use_blue_arg() -> i32:
            return use_blue_arg(step(1), 5)

        # ------------
        def combine(a: i32, b: i32) -> i32:
            return a * 10 + b

        def call_nested() -> i32:
            return combine(drop_all_args(step(1), step(2), step(3)), step(4))

        # ------------
        def call_colors(x: i32) -> tuple[str, str, str]:
            n = drop_all_args(x, x, x)
            m = const_result(x, x)
            return COLOR(x), COLOR(n), COLOR(m)
        """
        mod = self.compile(src)
        assert mod.call_drop_all_args() == 42
        assert mod.get_log() == 123

        mod.reset()
        assert mod.call_const_result() == 42
        assert mod.get_log() == 12

        mod.reset()
        assert mod.call_use_blue_arg() == 5
        assert mod.get_log() == 1

        mod.reset()
        assert mod.call_nested() == 424
        assert mod.get_log() == 1234

        mod.reset()
        assert mod.call_colors(7) == ("red", "blue", "blue")
        assert mod.get_log() == 0

    def test_blue_AssingLocal_keeps_side_effects(self):
        src = """
        from operator import OpSpec

        @blue.metafunc
        def foo(m_x):
            return OpSpec.const(True)

        var calls: i32 = 0

        def reset() -> None:
            global calls
            calls = 0

        def get_calls() -> i32:
            return calls

        def bump() -> i32:
            global calls
            calls = calls + 1
            return calls

        def call_and() -> bool:
            y = foo(bump()) and True
            return y

        def call_or() -> bool:
            y = foo(bump()) or False
            return y

        def call_walrus() -> bool:
            y = (x := foo(bump()))
            return y
        """
        mod = self.compile(src)
        assert mod.call_and() is True
        assert mod.get_calls() == 1

        mod.reset()
        assert mod.call_or() is True
        assert mod.get_calls() == 1

        mod.reset()
        assert mod.call_walrus() is True
        assert mod.get_calls() == 1

    def test_blue_walrus_keeps_side_effects(self):
        src = """
        from operator import OpSpec

        @blue.metafunc
        def foo(m_x):
            return OpSpec.const(True)

        var calls: i32 = 0

        def get_calls() -> i32:
            return calls

        def bump() -> i32:
            global calls
            calls = calls + 1
            return calls

        def call_walrus() -> bool:
            return (x := foo(bump()))
        """
        mod = self.compile(src)
        assert mod.call_walrus() is True
        assert mod.get_calls() == 1

    def test_blue_VarDef_keeps_side_effects(self):
        src = """
        from operator import OpSpec

        @blue.metafunc
        def foo(m_x):
            return OpSpec.const(True)

        var calls: i32 = 0

        def get_calls() -> i32:
            return calls

        def bump() -> i32:
            global calls
            calls = calls + 1
            return calls

        def call_vardef() -> bool:
            const y = foo(bump())
            return y
        """
        mod = self.compile(src)
        assert mod.call_vardef() is True
        assert mod.get_calls() == 1
