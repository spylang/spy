from typing import Any
import fixedint
from spy.vm.object import W_Object, W_Type, W_void, W_i32

class Builtins:
    w_object: W_Type
    w_type: W_Type
    w_i32: W_Type
    w_void: W_Type
    w_None: W_void

class SPyVM:
    """
    A Virtual Machine to execute SPy code.
    """

    builtins: Builtins

    def __init__(self) -> None:
        self.init_builtins()

    def init_builtins(self) -> None:
        self.builtins = Builtins()
        self.builtins.w_object = W_Object._w
        self.builtins.w_type = W_Type._w
        self.builtins.w_i32 = W_i32._w
        self.builtins.w_void = W_void._w
        self.builtins.w_None = W_void._w_singleton

    def w_dynamic_type(self, w_obj: W_Object) -> W_Type:
        assert isinstance(w_obj, W_Object)
        return w_obj.spy_get_w_type(self)

    def issubclass(self, w_sub: W_Type, w_super: W_Type) -> bool:
        assert isinstance(w_super, W_Type)
        assert isinstance(w_sub, W_Type)
        w_class = w_sub
        while w_class is not self.builtins.w_None:
            if w_class is w_super:
                return True
            w_class = w_class.w_base  # type:ignore
        return False

    def wrap(self, value: Any) -> W_Object:
        """
        Useful for tests: magic funtion which wraps the given inter-level object
        into the most appropriate app-level W_* object.
        """
        if value is None:
            return self.builtins.w_None
        elif type(value) in (int, fixedint.Int32):
            return W_i32(value)
        elif isinstance(value, type) and issubclass(value, W_Object):
            return value._w
        raise Exception(f"Cannot wrap interp-level objects of type {value.__class__.__name__}")

    def unwrap(self, w_value: W_Object) -> Any:
        """
        Useful for tests: magic funtion which wraps the given app-level w_ object
        into the most appropriate inter-level object. Opposite of wrap().
        """
        assert isinstance(w_value, W_Object)
        return w_value.spy_unwrap(self)
