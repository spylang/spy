from spy.tests.support import CompilerTest, no_C


@no_C
class TestUnrollRange(CompilerTest):
    def test_basic(self):
        mod = self.compile("""
        from __spy__ import UNROLL_RANGE

        def foo() -> i32:
            acc = 0
            for i in UNROLL_RANGE(4):
                acc = acc + i
            return acc
        """)
        assert mod.foo() == 6  # 0+1+2+3

    def test_vardef_in_body(self):
        mod = self.compile("""
        from __spy__ import UNROLL_RANGE

        def foo() -> i32:
            acc = 0
            for i in UNROLL_RANGE(4):
                const x = i * 3
                acc = acc + x
            return acc
        """)
        assert mod.foo() == 18  # (0+1+2+3)*3

    def test_zero_iterations(self):
        mod = self.compile("""
        from __spy__ import UNROLL_RANGE

        def foo() -> i32:
            acc = 0
            for i in UNROLL_RANGE(0):
                acc = acc + i
            return acc
        """)
        assert mod.foo() == 0
