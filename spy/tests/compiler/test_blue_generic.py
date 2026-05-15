from spy.fqn import FQN
from spy.tests.support import CompilerTest, expect_errors, only_interp


class TestBlueGeneric(CompilerTest):
    def test_blue_generic(self):
        mod = self.compile("""
        @blue.generic
        def add(T):
            def impl(x: T, y: T) -> T:
                return x + y
            return impl

        def foo() -> i32:
            return add[i32](1, 2)

        def bar() -> str:
            return add[str]('hello ', 'world')
        """)
        assert mod.foo() == 3
        assert mod.bar() == "hello world"

    def test_generic_args(self):
        mod = self.compile("""
        def add[T](x: T, y: T) -> T:
            return x + y

        def foo() -> i32:
            return add[i32](1, 2)

        def bar() -> str:
            return add[str]('hello ', 'world')
        """)
        assert mod.foo() == 3
        assert mod.bar() == "hello world"

    @only_interp
    def test_generic_type_origin(self):
        mod = self.compile("""
        @blue.generic
        def MyType(T):
            @struct
            class _impl:
                data: T
            return _impl

        def get_origin() -> dynamic:
            Concrete = MyType[i32]
            return Concrete.__origin__
        """)
        w_origin = mod.get_origin(unwrap=False)
        w_mod = self.vm.modules_w["test"]
        w_MyType = w_mod.getattr("MyType")
        assert w_origin is w_MyType

    @only_interp
    def test_non_generic_type_origin_is_none(self):
        mod = self.compile("""
        @struct
        class Foo:
            data: i32

        def get_origin() -> dynamic:
            return Foo.__origin__
        """)
        assert mod.get_origin() is None

    @only_interp
    def test_generic_origin_not_overwritten(self):
        mod = self.compile("""
        @blue.generic
        def Type(T):
            @struct
            class _impl:
                data: T
            return _impl

        @blue.generic
        def Bar(T):
            return Type[T]

        def get_origin() -> dynamic:
            return Bar[i32].__origin__
        """)
        w_origin = mod.get_origin(unwrap=False)
        w_mod = self.vm.modules_w["test"]
        w_Type = w_mod.getattr("Type")
        assert w_origin is w_Type

    @only_interp
    def test_generic_origin_not_set_for_external_type(self):
        mod = self.compile("""
        @struct
        class Outer:
            data: i32

        @blue.generic
        def passthrough(T):
            return Outer

        def get_origin() -> dynamic:
            return passthrough[i32].__origin__
        """)
        assert mod.get_origin() is None

    def test_cannot_call_blue_generic(self):
        src = """
        @blue.generic
        def ident(x):
            return x

        def foo() -> i32:
            return ident(42)
        """
        errors = expect_errors(
            "generic functions must be called via `[...]`",
            ("this is `@blue.generic def(dynamic) -> dynamic`", "ident"),
            ("`ident` defined here", "def ident(x):"),
        )
        self.compile_raises(src, "foo", errors)

    @only_interp
    def test_dynamic_alias_inner_type(self):
        mod = self.compile("""
        @blue.generic
        def MyList(T):
            @struct
            class _impl:
                x: T
            return _impl

        def get_type() -> type:
            return MyList[i32]
        """)
        w_mylist_i32 = mod.get_type(unwrap=False)
        impl_fqn = FQN("test::MyList[i32]::_impl")
        human_fqn = FQN("test::MyList[i32]")
        assert w_mylist_i32.fqn == impl_fqn
        assert self.vm.fqn_human_aliases[impl_fqn] == human_fqn
        assert impl_fqn.human_name(self.vm) == "test::MyList[i32]"

    @only_interp
    def test_builtins_fqn(self):
        mod = self.compile("""
        def get_list_type() -> type:
            return list[i32]

        def get_dict_type() -> type:
            return dict[i32, str]

        def get_tuple_type() -> type:
            return tuple[i32, str, float]
        """)
        w_list = mod.get_list_type(unwrap=False)
        w_dict = mod.get_dict_type(unwrap=False)
        w_tuple = mod.get_tuple_type(unwrap=False)

        assert w_list.fqn.human_name(self.vm) == "list[i32]"
        assert w_dict.fqn.human_name(self.vm) == "dict[i32, str]"
        assert w_tuple.fqn.human_name(self.vm) == "tuple[i32, str, f64]"
