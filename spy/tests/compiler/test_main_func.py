from contextlib import nullcontext
from typing import Any

import pytest

from spy.errors import SPyError
from spy.fqn import FQN
from spy.tests.support import (
    CompilerTest,
    expect_errors,
    no_C,
    only_interp,
    skip_backends,
)
from spy.vm.b import TYPES, B
from spy.vm.object import W_Type


@only_interp
class TestMainFunc(CompilerTest):
    def typecheck_main(self, src: str, ctx: Any = None) -> tuple[W_Type, bool]:
        mod = self.compile(src)
        w_main = mod.w_mod.getattr_maybe("main")
        if ctx is None:
            ctx = nullcontext()

        with ctx:
            return self.vm.typecheck_main(w_main)

    def test_return_None(self):
        src = """
        def main() -> None:
            pass
        """
        w_resT, has_argv = self.typecheck_main(src)
        assert w_resT is TYPES.w_NoneType
        assert not has_argv

    def test_return_i32(self):
        src = """
        def main() -> i32:
            return 0
        """
        w_resT, has_argv = self.typecheck_main(src)
        assert w_resT is B.w_i32
        assert not has_argv

    def test_return_int(self):
        src = """
        def main() -> int:
            return 0
        """
        w_resT, has_argv = self.typecheck_main(src)
        assert w_resT is B.w_i32
        assert not has_argv

    def test_argv(self):
        src = """
        def main(argv: list[str]) -> None:
            pass
        """
        w_resT, has_argv = self.typecheck_main(src)
        assert w_resT is TYPES.w_NoneType
        assert has_argv

    def test_argv_and_exit_code(self):
        src = """
        def main(argv: list[str]) -> i32:
            return 0
        """
        w_resT, has_argv = self.typecheck_main(src)
        assert w_resT is B.w_i32
        assert has_argv

    def test_invalid_return_type(self):
        src = """
        def main() -> str:
            pass
        """
        errors = expect_errors(
            "`main` has the wrong signature",
            ("the only valid return types are `None`, `int` and `i32`", "str"),
        )
        self.typecheck_main(src, errors)

    def test_invalid_param_type(self):
        src = """
        def main(x: i32) -> None:
            pass
        """
        errors = expect_errors(
            "`main` has the wrong signature",
            ("parameters must be `main(argv: list[str])`", "x: i32"),
        )
        self.typecheck_main(src, errors)

    def test_too_many_params(self):
        src = """
        def main(a: list[str], b: list[str]) -> None:
            pass
        """
        errors = expect_errors(
            "`main` has the wrong signature",
            (
                "parameters must be `main(argv: list[str])`",
                "a: list[str], b: list[str]",
            ),
        )
        self.typecheck_main(src, errors)
