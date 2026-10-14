import pytest

from spy.fqn import FQN
from spy.tests.support import CompilerTest
from spy.vm.struct import UnwrappedStruct


class TestWasmWrapper(CompilerTest):
    def test_return_to_python(self):
        src = r"""
        def foo() -> tuple[i32, i32, i32]:
            return 1, 2, 3

        def nested() -> tuple[i32, tuple[i32, i32]]:
            return 1, (2, 3)

        def mixed_type() -> tuple[i32, f64, bool, str, complex128]:
            return 1, 2.5, True, "hello", 2j

        def return_list_i32() -> list[i32]:
            return [1, 2, 3]

        def return_list_str() -> list[str]:
            return ["Hello", "SPy"]

        def return_dict() -> dict[i32, i32]:
            return {1: 10, 2: 20}
        """
        mod = self.compile(src)
        tup = mod.foo()
        assert tup == (1, 2, 3)

        tup = mod.nested()
        assert tup == (1, (2, 3))

        tup = mod.mixed_type()
        assert tup == (1, 2.5, True, "hello", 2j)

        assert mod.return_list_i32() == [1, 2, 3]
        assert mod.return_list_str() == ["Hello", "SPy"]
        assert mod.return_dict() == {1: 10, 2: 20}

    def test_wrong_number_of_arguments_from_python(self):
        mod = self.compile("""
        def inc(x: i32) -> i32:
            return x + 1
        """)
        with pytest.raises(TypeError, match="inc takes exactly 1 arguments, got 2"):
            mod.inc(1, 2)
        with pytest.raises(TypeError, match="inc takes exactly 1 arguments, got 0"):
            mod.inc()

    def test_pass_nested_struct_with_complex_field(self):
        src = """
        @struct
        class Cpx:
            z: complex128
            n: i32

        @struct
        class Outer:
            a: i32
            c: Cpx

        def foo(o: Outer) -> Outer:
            return Outer(o.a + 1, o.c)
        """
        mod = self.compile(src)
        inner = UnwrappedStruct(FQN("test::Cpx"), {"z": 1 + 2j, "n": 5})
        outer = UnwrappedStruct(FQN("test::Outer"), {"a": 10, "c": inner})
        assert mod.foo(outer) == (11, (1 + 2j, 5))
