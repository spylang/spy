import fixedint
import pytest
from spy.vm.vm import SPyVM
from spy.vm.b import B
from spy.fqn import QN, FQN
from spy.errors import SPyTypeError
from spy.vm.object import W_Object, W_Type, spytype, W_Void, W_I32, W_Bool
from spy.vm.str import W_Str
from spy.vm.function import W_BuiltinFunc
from spy.vm.module import W_Module

class TestVM:

    def test_W_Object(self):
        vm = SPyVM()
        w_obj = W_Object()
        assert repr(w_obj).startswith('<spy instance: type=object, id=')
        assert vm.dynamic_type(w_obj) is B.w_object

    def test_object_type_metaclass(self):
        # in the following, for each property of the SPy object model we also
        # show and test the corresponding property of the Python object model,
        # to make it clearer what it means
        vm = SPyVM()
        # the metaclass of <object> is <type>
        assert type(object) is type
        assert vm.dynamic_type(B.w_object) is B.w_type
        #
        # the metaclass of <type> is <type> itself
        assert type(type) is type
        assert vm.dynamic_type(B.w_type) is B.w_type
        #
        # <type> is a subclass of <object>
        assert type.__base__ is object
        assert B.w_type.w_base is B.w_object
        #
        # the base class of <object> is None
        assert object.__base__ is None
        assert B.w_object.w_base is B.w_None

    def test_dynamic(self):
        vm = SPyVM()
        assert B.w_dynamic.w_base is B.w_None
        assert vm.issubclass(B.w_object, B.w_dynamic)
        assert not vm.issubclass(B.w_dynamic, B.w_object)

    def test_W_Type_repr(self):
        vm = SPyVM()
        assert repr(B.w_object) == "<spy type 'object'>"
        assert repr(B.w_type) == "<spy type 'type'>"
        assert repr(B.w_dynamic) == "<spy type 'dynamic'>"

    def test_spytype_decorator(self):
        @spytype('foo')
        class W_Foo(W_Object):
            pass
        #
        assert isinstance(W_Foo._w, W_Type)
        assert W_Foo._w.name == 'foo'
        assert W_Foo._w.pyclass is W_Foo

    def test_w_base(self):
        @spytype('A')
        class W_A(W_Object):
            pass
        #
        @spytype('B')
        class W_B(W_A):
            pass
        #
        w_None = W_Void._w_singleton
        assert W_Object._w.w_base is w_None
        assert W_A._w.w_base is W_Object._w
        assert W_B._w.w_base is W_A._w

    def test_issubclass(self):
        @spytype('A')
        class W_A(W_Object):
            pass
        #
        @spytype('B')
        class W_B(W_A):
            pass
        #
        vm = SPyVM()
        w_a = W_A._w
        w_b = W_B._w
        #
        assert vm.issubclass(w_a, B.w_object)
        assert vm.issubclass(w_b, B.w_object)
        assert vm.issubclass(w_a, w_a)
        assert vm.issubclass(w_b, w_b)
        assert vm.issubclass(w_b, w_a)
        assert not vm.issubclass(w_a, w_b)

    def test_wrap_unwrap_types(self):
        vm = SPyVM()
        assert vm.wrap(W_Object) is B.w_object
        assert vm.unwrap(B.w_object) is W_Object
        #
        # check that wrapping an unsupported type raises
        class Foo:
            pass
        with pytest.raises(Exception,
                           match="Cannot wrap interp-level objects of type Foo"):
            vm.wrap(Foo())

    def test_w_None(self):
        vm = SPyVM()
        w_None = B.w_None
        assert isinstance(w_None, W_Void)
        assert vm.dynamic_type(w_None).name == 'void'
        assert repr(w_None) == '<spy None>'
        #
        assert vm.wrap(None) is w_None

    def test_W_I32(self):
        vm = SPyVM()
        w_x = vm.wrap(123)
        w_y = vm.wrap(fixedint.Int32(456))
        assert isinstance(w_x, W_I32)
        assert vm.dynamic_type(w_x) is B.w_i32
        assert repr(w_x) == 'W_I32(123)'
        assert repr(B.w_i32) == "<spy type 'i32'>"
        #
        x = vm.unwrap(w_x)
        y = vm.unwrap(w_y)
        assert x == 123
        assert y == 456
        assert type(x) is fixedint.Int32
        assert type(y) is fixedint.Int32
        #
        # check that we are actually using 32bit fixed arithmetic
        w_z = vm.wrap(0xffffffff)
        z = vm.unwrap(w_z)
        assert z == -1

    def test_W_Bool(self):
        vm = SPyVM()
        w_True = vm.wrap(True)
        w_False = vm.wrap(False)
        assert isinstance(w_True, W_Bool)
        assert isinstance(w_False, W_Bool)
        #
        # w_True and w_False are singletons
        assert vm.wrap(True) is w_True
        assert vm.wrap(False) is w_False
        assert vm.unwrap(w_True) is True
        assert vm.unwrap(w_False) is False
        #
        assert vm.dynamic_type(w_True) is B.w_bool
        assert repr(w_True) == 'W_Bool(True)'
        assert repr(w_False) == 'W_Bool(False)'
        assert repr(B.w_bool) == "<spy type 'bool'>"

    def test_W_Str(self):
        vm = SPyVM()
        w_hello = vm.wrap('hello')
        assert isinstance(w_hello, W_Str)
        assert vm.dynamic_type(w_hello) is B.w_str
        assert vm.unwrap(w_hello) == 'hello'
        assert repr(w_hello) == "W_Str('hello')"

    def test_call_function(self):
        vm = SPyVM()
        w_abs = B.w_abs
        w_x = vm.wrap(-42)
        w_y = vm.call_function(w_abs, [w_x])
        assert vm.unwrap(w_y) == 42

    def test_call_function_TypeError(self):
        vm = SPyVM()
        w_abs = B.w_abs
        w_x = vm.wrap('hello')
        msg = 'Invalid cast. Expected `i32`, got `str`'
        with pytest.raises(SPyTypeError, match=msg):
            vm.call_function(w_abs, [w_x])

    def test_get_FQN(self):
        vm = SPyVM()
        w_mod = W_Module(vm, "test", "...")
        vm.register_module(w_mod)
        #
        # the first global is "plain" (suffix=="")
        a = vm.get_FQN(QN("test::a"), is_global=True)
        assert a.fullname == "test::a"
        # but if we add a conflicting global, we need to add a suffix
        a1 = vm.get_FQN(QN("test::a"), is_global=True)
        assert a1.fullname == "test::a#1"
        #
        # for non-globals, we always put a suffix
        b0 = vm.get_FQN(QN("test::b"), is_global=False)
        assert b0.fullname == "test::b#0"
        b1 = vm.get_FQN(QN("test::b"), is_global=False)
        assert b1.fullname == "test::b#1"

    def test_eq(self):
        vm = SPyVM()
        w_a = vm.wrap(1)
        w_b = vm.wrap(1)
        w_c = vm.wrap(2)
        assert vm.is_True(vm.eq(w_a, w_a))
        assert vm.is_True(vm.eq(w_a, w_b))
        assert vm.is_False(vm.eq(w_a, w_c))
