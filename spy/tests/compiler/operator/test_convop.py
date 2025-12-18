from typing import Annotated

from spy.tests.support import CompilerTest, no_C
from spy.vm.b import TYPES, B
from spy.vm.builtin import builtin_method
from spy.vm.member import Member
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_I32
from spy.vm.registry import ModuleRegistry
from spy.vm.vm import SPyVM
from spy.vm.w import W_Object, W_Str, W_Type


class W_MyClass(W_Object):
    w_x: Annotated[W_I32, Member("x")]

    def __init__(self, w_x: W_I32) -> None:
        self.w_x = w_x

    @builtin_method("__new__")
    @staticmethod
    def w_new(vm: "SPyVM", w_x: W_I32) -> "W_MyClass":
        return W_MyClass(w_x)

    @builtin_method("__convert_to__", color="blue", kind="metafunc")
    @staticmethod
    def w_CONVERT_TO(
        vm: "SPyVM", wam_expT: W_MetaArg, wam_gotT: W_MetaArg, wam_self: W_MetaArg
    ) -> W_OpSpec:
        w_expT = wam_expT.w_blueval
        w_gotT = wam_gotT.w_blueval
        assert w_gotT is W_MyClass._w
        assert w_gotT is wam_self.w_static_T

        if w_expT is B.w_i32:
            # test_convert_to: simple OpSpec
            @vm.register_builtin_func("ext")
            def w_to_i32(vm: "SPyVM", w_self: W_MyClass) -> W_I32:
                return w_self.w_x

            return W_OpSpec(w_to_i32)

        elif w_expT is B.w_str:
            # test_complex_OpSpec2: complex OpSpec which also uses expT
            @vm.register_builtin_func("ext")
            def w_to_str(vm: "SPyVM", w_expT: W_Type, w_self: W_MyClass) -> W_Str:
                t = w_expT.fqn.human_name
                x = vm.unwrap_i32(w_self.w_x)
                return vm.wrap(f"<conv {x} to {t}>")

            return W_OpSpec(w_to_str, [wam_expT, wam_self])

        else:
            return W_OpSpec.NULL

    @builtin_method("__convert_from__", color="blue", kind="metafunc")
    @staticmethod
    def w_CONVERT_FROM(
        vm: "SPyVM", wam_expT: W_MetaArg, wam_gotT: W_MetaArg, wam_val: W_MetaArg
    ) -> W_OpSpec:
        w_expT = wam_expT.w_blueval
        w_gotT = wam_gotT.w_blueval
        assert w_expT is W_MyClass._w

        if w_gotT is B.w_i32:
            # test_convert_from: simple OpSpec
            @vm.register_builtin_func("ext")
            def w_from_i32(vm: "SPyVM", w_val: W_I32) -> W_MyClass:
                return W_MyClass(w_val)

            return W_OpSpec(w_from_i32)

        elif w_gotT is TYPES.w_NoneType:
            # test_complex_OpSpec1: complex OpSpec with non-default args
            @vm.register_builtin_func("ext")
            def w_from_None(vm: "SPyVM") -> W_MyClass:
                w_x = vm.wrap(-1)
                return W_MyClass(w_x)

            return W_OpSpec(w_from_None, [])

        return W_OpSpec.NULL


@no_C
class TestConvop(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def setup_ext(self) -> None:
        EXT = ModuleRegistry("ext")
        EXT.builtin_type("MyClass")(W_MyClass)
        self.vm.make_module(EXT)

    def test_convert_to(self):
        self.setup_ext()
        src = """
        from ext import MyClass

        def convert_to_i32(x: i32) -> i32:
            obj = MyClass(x)
            return obj
        """
        mod = self.compile(src)
        assert mod.convert_to_i32(42) == 42

    def test_convert_from(self):
        self.setup_ext()
        src = """
        from ext import MyClass

        def convert_from_i32() -> MyClass:
            return 42
        """
        mod = self.compile(src)
        w_result = mod.convert_from_i32(unwrap=False)
        assert isinstance(w_result, W_MyClass)
        assert self.vm.unwrap_i32(w_result.w_x) == 42

    def test_convert_complex_OpSpec1(self):
        self.setup_ext()
        src = """
        from ext import MyClass

        def convert_from_None() -> MyClass:
            return None
        """
        mod = self.compile(src)
        w_result = mod.convert_from_None(unwrap=False)
        assert isinstance(w_result, W_MyClass)
        assert self.vm.unwrap_i32(w_result.w_x) == -1

    def test_convert_complex_OpSpec2(self):
        self.setup_ext()
        src = """
        from ext import MyClass

        def convert_to_str_return(x: i32) -> str:
            obj = MyClass(x)
            return obj

        def convert_to_str_local(x: i32) -> str:
            obj = MyClass(x)
            s: str = obj
            return s

        def convert_to_str_arg(x: i32) -> str:
            obj = MyClass(x)
            return as_str(obj)

        def as_str(x: str) -> str:
            return x
        """
        mod = self.compile(src)
        res = mod.convert_to_str_return(42)
        assert res == "<conv 42 to str>"
        #
        res = mod.convert_to_str_local(43)
        assert res == "<conv 43 to str>"
        #
        res = mod.convert_to_str_arg(44)
        assert res == "<conv 44 to str>"
