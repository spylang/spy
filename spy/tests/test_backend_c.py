"""
Unit tests for the C backend.

This is just a small part of the tests: the majority of the functionality is
tested by tests/compiler/*.py.
"""

import textwrap

import py.path
import pytest

from spy.backend.c.c_ast import BinOp, Literal, UnaryOp, make_table
from spy.backend.c.cbackend import CBackend
from spy.backend.c.context import C_Ident
from spy.build.config import BuildConfig
from spy.fqn import FQN
from spy.vm.vm import SPyVM


class TestCBackend:
    @pytest.fixture
    def vm(self, tmpdir):
        self.tmpdir = tmpdir
        vm = SPyVM()
        vm.path.append(str(tmpdir))
        return vm

    def compile_until_CBackend(self, vm: SPyVM, src: str) -> CBackend:
        # XXX: there is a lot of code duplication with other similar tests
        modname = "test"
        srcfile = self.tmpdir.join(f"{modname}.spy")
        srcfile.write(textwrap.dedent(src))
        vm.import_(modname)
        vm.redshift(error_mode="eager")
        builddir = self.tmpdir.join("build").ensure(dir=True)
        config = BuildConfig(target="wasi", kind="lib", build_type="debug", opt_level=0)
        backend = CBackend(vm, modname, config, builddir, dump_c=False)
        return backend

    def test_make_table(self):
        table = make_table("""
        12: * /
        11: + -
         8: ==
        """)
        assert table == {
            "*": 12,
            "/": 12,
            "+": 11,
            "-": 11,
            "==": 8,
        }

    def test_BinOp1(self):
        # fmt: off
        expr = BinOp("*",
            left = BinOp("+",
                left = Literal("1"),
                right = Literal("2")
            ),
            right = Literal("3")
        )
        # fmt: on
        assert str(expr) == "(1 + 2) * 3"

    def test_BinOp2(self):
        # fmt: off
        expr = BinOp("*",
            left = Literal("1"),
            right = BinOp("+",
                left = Literal("2"),
                right = BinOp("*",
                    left = Literal("3"),
                    right = Literal("4")
                )
            )
        )
        # fmt: on
        assert str(expr) == "1 * (2 + 3 * 4)"

    def test_UnaryOp(self):
        # fmt: off
        expr = UnaryOp("-",
            value=BinOp("*",
                left=Literal("1"),
                right=Literal("2"),
            ),
        )
        # fmt: on
        assert str(expr) == "-(1 * 2)"

    def test_Literal_from_bytes(self):
        def cstr(b: bytes) -> str:
            return str(Literal.from_bytes(b))

        #
        assert cstr(b"--hello--") == '"--hello--"'
        assert cstr(b'--"hello"--') == r'"--\"hello\"--"'
        assert cstr(rb"--aa\bb--") == r'"--aa\\bb--"'
        assert cstr(b"--\x00--\n--\xff--") == r'"--\x00--\x0a--\xff--"'
        assert cstr(b"\nball") == r'"\x0a""ball"'
        assert cstr(b"ball\n") == r'"ball\x0a"'
        assert cstr(b"ball\n\nball") == r'"ball\x0a\x0a""ball"'
        assert cstr(b"\x00\x01\x02") == r'"\x00\x01\x02"'

    def test_C_Ident(self):
        assert str(C_Ident("hello")) == "hello"
        assert str(C_Ident("default")) == "default$"

    def test_struct_deps(self, vm):
        src = """
        from unsafe import gc_ptr

        @struct
        class Color:
            name: str

        @struct
        class Point:
            x: i32
            y: i32

        @struct
        class Rect:
            a: Point
            b: Point
            color: gc_ptr[Color]
        """
        backend = self.compile_until_CBackend(vm, src)

        def deps(fqn_str: str) -> list[str]:
            return [str(d) for d in backend.get_type_deps(FQN(fqn_str))]

        # A struct containing only primitive/pointer fields has no by-value
        # type deps. Pointers do NOT count as dependencies, since we already
        # emit a forward declaration for the pointee type.
        assert deps("test::Color") == []
        assert deps("test::Point") == []
        assert deps("test::Rect") == ["test::Point"]

    def test_topo_sort(self, vm):
        # `Inner` is created lazily by Vec2[i32], so it ends up in
        # vm.globals_w AFTER `Outer` even though `Outer` has it as a
        # by-value field. Without the topo sort, the C backend would emit
        # Outer before Inner and produce broken code.
        src = """
        @blue.generic
        def Vec2(T):
            @struct
            class Inner:
                a: T
                b: T
            return Inner

        @struct
        class Outer:
            v: Vec2[i32]

        def foo() -> i32:
            o = Outer.__make__(Vec2[i32].__make__(1, 2))
            return o.v.a + o.v.b
        """
        backend = self.compile_until_CBackend(vm, src)
        backend.split_fqns()
        order = [str(fqn) for fqn, _ in backend.c_structdefs["globals"].content]
        i_inner = order.index("test::Vec2[i32]::Inner")
        i_outer = order.index("test::Outer")
        assert i_inner < i_outer
