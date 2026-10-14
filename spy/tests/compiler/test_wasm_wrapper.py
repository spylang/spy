import pytest

from spy.fqn import FQN
from spy.tests.support import CompilerTest
from spy.vm.struct import UnwrappedStruct


class TestWasmWrapper(CompilerTest):
    def test_return_to_python(self):
        src = r"""
        def return_tuple() -> tuple[i32, i32, i32]:
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
        assert mod.return_tuple() == (1, 2, 3)
        assert mod.nested() == (1, (2, 3))
        assert mod.mixed_type() == (1, 2.5, True, "hello", 2j)
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

    def test_scalar_args_and_results(self):
        mod = self.compile("""
        def same[T](x: T) -> T:
            return x

        same_i32 = same[i32]
        same_i64 = same[i64]
        same_u8 = same[u8]
        same_u64 = same[u64]
        same_f64 = same[f64]
        same_c128 = same[complex128]

        def invert(x: bool) -> bool:
            return not x
        """)
        assert mod.same_i32(42) == 42
        assert mod.same_i64(42) == 42
        assert mod.same_u8(42) == 42
        assert mod.same_u64(42) == 42
        assert mod.same_f64(2.5) == 2.5
        assert mod.same_c128(1 + 2j) == 1 + 2j
        assert mod.invert(True) is False

    def test_str_bytes_and_rawbuffer(self):
        mod = self.compile("""
        from rawbuffer import RawBuffer, rb_alloc, rb_set_i32

        def str_len(s: str) -> i32:
            return len(s)

        def bytes_len(b: bytes) -> i32:
            return len(b)

        def echo_str(s: str) -> str:
            return s

        def echo_bytes(b: bytes) -> bytes:
            return b

        def make_rawbuffer() -> RawBuffer:
            buf: RawBuffer = rb_alloc(4)
            rb_set_i32(buf, 0, 0x01020304)
            return buf
        """)
        assert mod.str_len("hello") == 5
        assert mod.bytes_len(b"abc") == 3
        assert mod.echo_str("hello") == "hello"
        assert mod.echo_bytes(b"abc") == b"abc"
        assert mod.make_rawbuffer() == b"\x04\x03\x02\x01"

    def test_none_ptr_and_slice(self):
        mod = self.compile("""
        from unsafe import gc_alloc, gc_ptr

        def do_nothing() -> None:
            pass

        def take_none(x: None) -> i32:
            return 7

        def make_ptr() -> gc_ptr[i32]:
            p: gc_ptr[i32] = gc_alloc[i32](3)
            p[0] = 10
            p[1] = 20
            p[2] = 30
            return p

        def second(p: gc_ptr[i32]) -> i32:
            return p[1]

        def slice_stop(s: slice) -> i32:
            return s.stop
        """)
        assert mod.do_nothing() is None
        assert mod.take_none(None) == 7
        p = mod.make_ptr()
        assert p.length == 3
        assert mod.second(p) == 20
        assert mod.slice_stop(slice(1, 7, None)) == 7

    def test_globals_and_repr(self):
        mod = self.compile("""
        var x: i32 = 42
        """)
        assert mod.x == 42
        if self.backend == "C":
            assert repr(mod).startswith("<WasmModuleWrapper")
        else:
            assert repr(mod).startswith("<spy.backend.interp.InterpModuleWrapper")
