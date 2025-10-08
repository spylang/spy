from typing import Annotated

from spy.tests.support import CompilerTest, expect_errors, no_C
from spy.vm.builtin import builtin_method
from spy.vm.member import Member
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_I32
from spy.vm.registry import ModuleRegistry
from spy.vm.vm import SPyVM
from spy.vm.w import W_Object, W_Type


@no_C
class TestCallOp(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def test_w_new_simple(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_type("Point")
        class W_Point(W_Object):
            w_x: Annotated[W_I32, Member("x")]
            w_y: Annotated[W_I32, Member("y")]

            def __init__(self, w_x: W_I32, w_y: W_I32) -> None:
                self.w_x = w_x
                self.w_y = w_y

            @builtin_method("__new__")
            @staticmethod
            def w_new(vm: "SPyVM", w_x: W_I32, w_y: W_I32) -> "W_Point":
                return W_Point(w_x, w_y)

        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import Point

        @blue
        def foo(x: i32, y: i32) -> i32:
            p = Point(x, y)
            return p.x * 10 + p.y
        """)
        res = mod.foo(3, 6)
        assert res == 36

    def test_w_new_metafunc(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_type("Point")
        class W_Point(W_Object):
            w_x: Annotated[W_I32, Member("x")]
            w_y: Annotated[W_I32, Member("y")]

            def __init__(self, w_x: W_I32, w_y: W_I32) -> None:
                self.w_x = w_x
                self.w_y = w_y

            @builtin_method("__new__", color="blue", kind="metafunc")
            @staticmethod
            def w_NEW(
                vm: "SPyVM", wam_cls: W_MetaArg, *args_wam: W_MetaArg
            ) -> W_OpSpec:
                # Support overloading based on argument count
                if len(args_wam) == 1:
                    # Point(x) -> Point(x, x)
                    @vm.register_builtin_func("ext", "new_point_single")
                    def w_new(vm: "SPyVM", w_cls: W_Type, w_x: W_I32) -> W_Point:
                        return W_Point(w_x, w_x)

                    return W_OpSpec(w_new)
                else:
                    # Normal Point(x, y)
                    @vm.register_builtin_func("ext", "new_point")
                    def w_new(
                        vm: "SPyVM", w_cls: W_Type, w_x: W_I32, w_y: W_I32
                    ) -> W_Point:
                        return W_Point(w_x, w_y)

                    return W_OpSpec(w_new)

        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import Point

        @blue
        def test_two_args(x: i32, y: i32) -> i32:
            p = Point(x, y)
            return p.x * 10 + p.y

        @blue
        def test_one_arg(x: i32) -> i32:
            p = Point(x)
            return p.x * 10 + p.y
        """)

        # Test with two args
        res = mod.test_two_args(3, 6)
        assert res == 36

        # Test with one arg (x=7)
        # Should create Point(7, 7)
        res = mod.test_one_arg(7)
        assert res == 77  # 7*10 + 7 = 77

    def test_no_w_new(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_type("MyClass")
        class W_MyClass(W_Object):
            pass

        # ========== /EXT module for this test =========

        self.vm.make_module(EXT)
        src = """
        from ext import MyClass

        def foo() -> MyClass:
            return MyClass()
        """
        errors = expect_errors(
            "cannot instantiate `ext::MyClass`",
            ("`ext::MyClass` does not have a method `__new__`", "MyClass"),
        )
        self.compile_raises(src, "foo", errors)

    def test_cannot_instantiate_red_class(self):
        src = """
        def bar(T: type) -> dynamic:
            return T()

        def foo() -> dynamic:
            return bar(i32)
        """
        errors = expect_errors(
            "instantiation of red types is not yet supported",
            ("this is red", "T"),
        )
        self.compile_raises(src, "foo", errors)

    def test_call_varargs(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_func
        def w_sum(vm: "SPyVM", *args_w: W_I32) -> W_I32:
            tot = 0
            for w_x in args_w:
                tot += vm.unwrap_i32(w_x)
            return vm.wrap(tot)

        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import sum

        def foo(x: i32) -> i32:
            return sum(x, 1, 2, 3)
        """)
        assert mod.foo(10) == 16

    def test_call_instance(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_type("Adder")
        class W_Adder(W_Object):
            def __init__(self, x: int) -> None:
                self.x = x

            @builtin_method("__new__")
            @staticmethod
            def w_new(vm: "SPyVM", w_x: W_I32) -> "W_Adder":
                return W_Adder(vm.unwrap_i32(w_x))

            @builtin_method("__call__")
            @staticmethod
            def w_call(vm: "SPyVM", w_obj: "W_Adder", w_y: W_I32) -> W_I32:
                y = vm.unwrap_i32(w_y)
                res = w_obj.x + y
                return vm.wrap(res)

        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import Adder

        def foo(x: i32, y: i32) -> i32:
            obj = Adder(x)
            return obj(y)
        """)
        x = mod.foo(5, 7)
        assert x == 12

    def test_call_method(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_type("Calc")
        class W_Calc(W_Object):
            def __init__(self, x: int) -> None:
                self.x = x

            @builtin_method("__new__")
            @staticmethod
            def w_new(vm: "SPyVM", w_x: W_I32) -> "W_Calc":
                return W_Calc(vm.unwrap_i32(w_x))

            @builtin_method("__call_method__", color="blue", kind="metafunc")
            @staticmethod
            def w_CALL_METHOD(
                vm: "SPyVM",
                wam_obj: W_MetaArg,
                wam_method: W_MetaArg,
                *args_wam: W_MetaArg,
            ) -> W_OpSpec:
                meth = wam_method.blue_unwrap_str(vm)
                if meth == "add":

                    @vm.register_builtin_func("ext", "add")
                    def w_fn(vm: "SPyVM", w_self: W_Calc, w_arg: W_I32) -> W_I32:
                        y = vm.unwrap_i32(w_arg)
                        return vm.wrap(w_self.x + y)

                    return W_OpSpec(w_fn, [wam_obj] + list(args_wam))

                elif meth == "sub":

                    @vm.register_builtin_func("ext", "sub")
                    def w_fn(vm: "SPyVM", w_self: W_Calc, w_arg: W_I32) -> W_I32:
                        y = vm.unwrap_i32(w_arg)
                        return vm.wrap(w_self.x - y)

                    return W_OpSpec(w_fn, [wam_obj] + list(args_wam))
                else:
                    return W_OpSpec.NULL

        # ========== /EXT module for this test =========

        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import Calc

        def foo(x: i32, y: i32, z: i32) -> i32:
            obj = Calc(x)
            return obj.add(y) * 10 + obj.sub(z)
        """)
        x = mod.foo(5, 1, 2)
        assert x == 63
