import fixedint
import pytest
from spy.vm.vm import SPyVM
from spy.vm.object import W_Object, W_Type, spytype, W_void, W_i32, W_bool
from spy.vm.str import W_str

class TestVM:

    def test_W_Object(self):
        vm = SPyVM()
        w_obj = W_Object()
        assert repr(w_obj).startswith('<spy instance: type=object, id=')
        assert vm.dynamic_type(w_obj) is vm.builtins.w_object

    def test_object_type_metaclass(self):
        # in the following, for each property of the SPy object model we also
        # show and test the corresponding property of the Python object model,
        # to make it clearer what it means
        vm = SPyVM()
        B = vm.builtins
        #
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

    def test_W_Type_repr(self):
        vm = SPyVM()
        assert repr(vm.builtins.w_object) == "<spy type 'object'>"
        assert repr(vm.builtins.w_type) == "<spy type 'type'>"

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
        w_None = W_void._w_singleton
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
        assert vm.issubclass(w_a, vm.builtins.w_object)
        assert vm.issubclass(w_b, vm.builtins.w_object)
        assert vm.issubclass(w_a, w_a)
        assert vm.issubclass(w_b, w_b)
        assert vm.issubclass(w_b, w_a)
        assert not vm.issubclass(w_a, w_b)

    def test_wrap_unwrap_types(self):
        vm = SPyVM()
        assert vm.wrap(W_Object) is vm.builtins.w_object
        assert vm.unwrap(vm.builtins.w_object) is W_Object
        #
        # check that wrapping an unsupported type raises
        class Foo:
            pass
        with pytest.raises(Exception,
                           match="Cannot wrap interp-level objects of type Foo"):
            vm.wrap(Foo())

    def test_w_None(self):
        vm = SPyVM()
        w_None = vm.builtins.w_None
        assert isinstance(w_None, W_void)
        assert vm.dynamic_type(w_None).name == 'void'
        assert repr(w_None) == '<spy None>'
        #
        assert vm.wrap(None) is w_None

    def test_W_i32(self):
        vm = SPyVM()
        w_x = vm.wrap(123)
        w_y = vm.wrap(fixedint.Int32(456))
        assert isinstance(w_x, W_i32)
        assert vm.dynamic_type(w_x) is vm.builtins.w_i32
        assert repr(w_x) == 'W_i32(123)'
        assert repr(vm.builtins.w_i32) == "<spy type 'i32'>"
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

    def test_W_bool(self):
        vm = SPyVM()
        w_True = vm.wrap(True)
        w_False = vm.wrap(False)
        assert isinstance(w_True, W_bool)
        assert isinstance(w_False, W_bool)
        #
        # w_True and w_False are singletons
        assert vm.wrap(True) is w_True
        assert vm.wrap(False) is w_False
        assert vm.unwrap(w_True) is True
        assert vm.unwrap(w_False) is False
        #
        assert vm.dynamic_type(w_True) is vm.builtins.w_bool
        assert repr(w_True) == 'W_bool(True)'
        assert repr(w_False) == 'W_bool(False)'
        assert repr(vm.builtins.w_bool) == "<spy type 'bool'>"

    def test_W_str(self):
        vm = SPyVM()
        w_hello = vm.wrap('hello')
        assert isinstance(w_hello, W_str)
        assert vm.dynamic_type(w_hello) is vm.builtins.w_str
        assert vm.unwrap(w_hello) == 'hello'
        assert repr(w_hello) == "W_str('hello')"
