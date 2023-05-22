from spy.vm.objects import W_Object, W_Type

class Builtins:
    pass

class SPyVM:
    """
    A Virtual Machine to execute SPy code.
    """

    def __init__(self):
        self.init_builtins()

    def init_builtins(self):
        self.builtins = Builtins()
        self.builtins.w_object = W_Object._w
        self.builtins.w_type = W_Type._w

    def w_dynamic_type(self, w_obj):
        assert isinstance(w_obj, W_Object)
        pyclass = type(w_obj)
        assert pyclass._w is not None
        return pyclass._w

    def issubclass(self, w_sub, w_super):
        assert isinstance(w_super, W_Type)
        assert isinstance(w_sub, W_Type)
        w_class = w_sub
        while w_class is not None:
            if w_class is w_super:
                return True
            w_class = w_class.w_base
        return False

    def wrap(self, value):
        """
        Useful for tests: magic funtion which wraps the given inter-level object
        into the most appropriate app-level W_* object.
        """
        if isinstance(value, type) and issubclass(value, W_Object):
            return value._w
        raise Exception(f"Cannot wrap inter-level objects of type {value.__class__.__name__}")

    def unwrap(self, w_value):
        """
        Useful for tests: magic funtion which wraps the given app-level w_ object
        into the most appropriate inter-level object. Opposite of wrap().
        """
        assert isinstance(w_value, W_Object)
        if isinstance(w_value, W_Type):
            return w_value.pyclass
        #
        spy_type = self.w_dynamic_type(w_value).name
        py_type = w_value.__class__.__name__
        raise Exception(f"Cannot unwrap app-level objects of type {spy_type} (inter-level type: {py_type})")
