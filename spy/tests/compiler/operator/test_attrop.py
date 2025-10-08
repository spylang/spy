from typing import Annotated

import pytest

from spy.tests.support import CompilerTest, expect_errors, no_C
from spy.vm.b import B
from spy.vm.builtin import (
    builtin_class_attr,
    builtin_classmethod,
    builtin_method,
    builtin_property,
    builtin_staticmethod,
)
from spy.vm.member import Member
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.primitive import W_I32
from spy.vm.registry import ModuleRegistry
from spy.vm.vm import SPyVM
from spy.vm.w import W_F64, W_Object, W_Str, W_Type


@no_C
class TestAttrOp(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    def test_member(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_type("MyClass")
        class W_MyClass(W_Object):
            w_x: Annotated[W_I32, Member("x")]

            def __init__(self) -> None:
                self.w_x = W_I32(0)

            @builtin_method("__new__")
            @staticmethod
            def w_new(vm: "SPyVM") -> "W_MyClass":
                return W_MyClass()
        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import MyClass

        @blue
        def foo():
            obj =  MyClass()
            obj.x = 123
            return obj.x
        """)
        x = mod.foo()
        assert x == 123

    def test_class_attribute(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_type("MyClass")
        class W_MyClass(W_Object):
            w_x = builtin_class_attr("x", self.vm.wrap(42))

            @builtin_method("__new__")
            @staticmethod
            def w_new(vm: "SPyVM") -> "W_MyClass":
                return W_MyClass()
        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)

        src1 = """
        from ext import MyClass
        def get_MyClass_x() -> i32:
            return MyClass.x

        def get_instance_x() -> i32:
            obj = MyClass()
            return obj.x
        """
        mod1 = self.compile(src1, modname="test1")
        assert mod1.get_MyClass_x() == 42
        assert mod1.get_instance_x() == 42

        src2 = """
        from ext import MyClass
        def get_foobar() -> i32:
            # foobar doesn't exist
            return MyClass.foobar
        """
        errors = expect_errors(
            "type `type` has no attribute 'foobar'",
            ("this is `type`", "MyClass"),
        )
        self.compile_raises(src2, "get_foobar", errors, modname="test2")


    def test_builtin_staticmethod_classmethod(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_type("MyClass")
        class W_MyClass(W_Object):
            w_x: Annotated[W_I32, Member("x")]

            def __init__(self, w_x: W_I32) -> None:
                self.w_x = w_x

            @builtin_staticmethod("from_int")
            @staticmethod
            def w_from_int(vm: "SPyVM", w_x: W_I32) -> "W_MyClass":
                return W_MyClass(w_x)

            @builtin_classmethod("from_float")
            @staticmethod
            def w_from_float(vm: "SPyVM", w_cls: W_Type,
                             w_f: W_F64) -> "W_MyClass":
                assert w_cls is W_MyClass._w
                f = vm.unwrap_f64(w_f)
                w_x = vm.wrap(int(f))
                return W_MyClass(w_x)

        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)

        src = """
        from ext import MyClass

        def foo(x: i32) -> i32:
            obj = MyClass.from_int(x)
            return obj.x

        def bar(x: f64) -> f64:
            obj = MyClass.from_float(x)
            return obj.x
        """
        mod = self.compile(src)
        assert mod.foo(10) == 10
        assert mod.bar(12.3) == 12

    def test_descriptor_get_set(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_type("MyProxy")
        class W_Adder(W_Object):
            n: int

            def __init__(self, n: int) -> None:
                self.n = n

            @builtin_method("__get__")
            @staticmethod
            def w_get(vm: "SPyVM", w_self: "W_Adder",
                      w_obj: W_Object) -> W_I32:
                assert isinstance(w_obj, W_MyClass)
                return vm.wrap(w_obj.val + w_self.n)

            @builtin_method("__set__")
            @staticmethod
            def w_set(vm: "SPyVM", w_self: "W_Adder",
                      w_obj: W_Object, w_val: W_I32) -> None:
                assert isinstance(w_obj, W_MyClass)
                val = vm.unwrap_i32(w_val)
                w_obj.val = val - w_self.n


        @EXT.builtin_type("MyClass")
        class W_MyClass(W_Object):
            w_val = builtin_class_attr("val", W_Adder(0))
            w_x = builtin_class_attr("x", W_Adder(32))

            def __init__(self) -> None:
                self.val = 10

            @builtin_method("__new__")
            @staticmethod
            def w_new(vm: "SPyVM") -> "W_MyClass":
                return W_MyClass()


        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import MyClass

        @blue
        def get_val():
            obj = MyClass()
            return obj.val

        @blue
        def get_x():
            obj = MyClass()
            return obj.x

        @blue
        def set_x_and_get_val():
            obj = MyClass()
            obj.x = 32
            return obj.val
        """)
        assert mod.get_val() == 10
        assert mod.get_x() == 42
        assert mod.set_x_and_get_val() == 0

    def test_instance_property(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_type("MyClass")
        class W_MyClass(W_Object):

            def __init__(self, x: int) -> None:
                self.x = x

            @builtin_method("__new__")
            @staticmethod
            def w_new(vm: "SPyVM", w_x: W_I32) -> "W_MyClass":
                x = vm.unwrap_i32(w_x)
                return W_MyClass(x)

            @builtin_property("x")
            @staticmethod
            def w_get_x(vm: "SPyVM", w_self: "W_MyClass") -> W_I32:
                return vm.wrap(w_self.x)

            @builtin_property("x2", color="blue", kind="metafunc")
            @staticmethod
            def w_GET_x2(vm: "SPyVM", wam_self: "W_MetaArg") -> W_OpSpec:
                """
                This exist just to test that we can have a metafunc as a
                @builtin_property
                """
                w_t = wam_self.w_static_T
                assert W_MyClass._w is w_t
                @vm.register_builtin_func(w_t.fqn, "get_y")
                def w_get_x2(vm: "SPyVM", w_self: W_MyClass) -> W_I32:
                    return vm.wrap(w_self.x * 2)
                return W_OpSpec(w_get_x2, [wam_self])


        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile(
        """
        from ext import MyClass

        @blue
        def get_x():
            obj = MyClass(42)
            return obj.x

        @blue
        def get_x2():
            obj = MyClass(43)
            return obj.x2
        """)
        x = mod.get_x()
        assert x == 42
        x2 = mod.get_x2()
        assert x2 == 86


    @pytest.mark.skip(reason="implement me")
    def test_class_property(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_type("MyClass")
        class W_MyClass(W_Object):

            @builtin_method("__new__")
            @staticmethod
            def w_new(vm: "SPyVM") -> "W_MyClass":
                return W_MyClass()

            @builtin_property("NULL", color="blue", kind="metafunc")
            @staticmethod
            def w_GET_NULL(vm: "SPyVM", wam_self: "W_MetaArg") -> W_OpSpec:
                raise NotImplementedError("WIP")


        # ========== /EXT module for this test =========
        self.vm.make_module(EXT)
        mod = self.compile(
        """
        from ext import MyClass

        @blue
        def get_NULL():
            return MyClass.NULL

        """)
        x = mod.get_NULL()
        breakpoint()

    def test_getattr_setattr_custom(self):
        # ========== EXT module for this test ==========
        EXT = ModuleRegistry("ext")

        @EXT.builtin_type("MyClass")
        class W_MyClass(W_Object):

            def __init__(self) -> None:
                self.x = 0

            @builtin_method("__new__")
            @staticmethod
            def w_new(vm: "SPyVM") -> "W_MyClass":
                return W_MyClass()

            @builtin_method("__getattribute__", color="blue", kind="metafunc")
            @staticmethod
            def w_GETATTRIBUTE(vm: "SPyVM", wam_obj: W_MetaArg,
                               wam_name: W_MetaArg) -> W_OpSpec:
                attr = wam_name.blue_unwrap_str(vm)
                if attr == "x":
                    @vm.register_builtin_func("ext", "getx")
                    def w_fn(vm: "SPyVM", w_obj: W_MyClass,
                           w_attr: W_Str) -> W_I32:
                        return vm.wrap(w_obj.x)
                else:
                    @vm.register_builtin_func("ext", "getany")
                    def w_fn(vm: "SPyVM", w_obj: W_MyClass,
                                      w_attr: W_Str) -> W_Str:
                        attr = vm.unwrap_str(w_attr)
                        return vm.wrap(attr.upper() + "--42")
                return W_OpSpec(w_fn)

            @builtin_method("__setattr__", color="blue", kind="metafunc")
            @staticmethod
            def w_SETATTR(vm: "SPyVM", wam_obj: W_MetaArg, wam_name: W_MetaArg,
                          wam_v: W_MetaArg) -> W_OpSpec:
                attr = wam_name.blue_unwrap_str(vm)
                if attr == "x":
                    @vm.register_builtin_func("ext")
                    def w_setx(vm: "SPyVM", w_obj: W_MyClass,
                               w_attr: W_Str, w_val: W_I32) -> None:
                        w_obj.x = vm.unwrap_i32(w_val)
                    return W_OpSpec(w_setx)
                else:
                    return W_OpSpec.NULL
        # ========== /EXT module for this test =========

        self.vm.make_module(EXT)
        mod = self.compile("""
        from ext import MyClass

        @blue
        def get_hello():
            obj = MyClass()
            return obj.hello

        def get_x() -> i32:
            obj = MyClass()
            return obj.x

        def set_get_x() -> i32:
            obj = MyClass()
            obj.x = 123
            return obj.x
        """)
        assert mod.get_hello() == "HELLO--42"
        assert mod.get_x() == 0
        assert mod.set_get_x() == 123
