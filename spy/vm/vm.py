from spy.vm.objects import W_Object, W_TypeObject

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
        self.builtins.w_type = W_TypeObject._w

    def w_dynamic_type(self, w_obj):
        assert isinstance(w_obj, W_Object)
        pyclass = type(w_obj)
        assert pyclass._w is not None
        return pyclass._w
