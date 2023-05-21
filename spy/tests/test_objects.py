from spy.vm.objects import W_Object, W_TypeObject
from spy.vm.vm import SPyVM

class TestObjects:

    def test_W_Object(self):
        vm = SPyVM()
        w_obj = W_Object()
        assert repr(w_obj).startswith('<spy instance: type=object, id=')
        assert vm.w_dynamic_type(w_obj) is vm.builtins.w_object

    def test_object_type_metaclass(self):
        # in the following, for each property of the SPy object model we also
        # show and test the corresponding property of the Python object model,
        # to make it clearer what it means
        vm = SPyVM()
        B = vm.builtins
        #
        # the metaclass of <object> is <type>
        assert type(object) is type
        assert vm.w_dynamic_type(B.w_object) is B.w_type
        #
        # the metaclass of <type> is <type> itself
        assert type(type) is type
        assert vm.w_dynamic_type(B.w_type) is B.w_type
        #
        # <type> is a subclass of <object>
        assert type.__base__ is object
        assert B.w_type.w_base is B.w_object

    def test_W_TypeObject_repr(self):
        vm = SPyVM()
        assert repr(vm.builtins.w_object) == "<spy type 'object'>"
        assert repr(vm.builtins.w_type) == "<spy type 'type'>"
