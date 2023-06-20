from typing import Any, Optional
import fixedint
from spy.vm.object import W_Object, W_Type, W_void, W_i32, W_str
from spy.vm.function import W_FunctionType, W_Function
from spy.vm.module import W_Module
from spy.vm.codeobject import W_CodeObject
from spy.vm.frame import Frame

class Builtins:
    w_object: W_Type
    w_type: W_Type
    w_i32: W_Type
    w_void: W_Type
    w_str: W_Type
    w_None: W_void

    def lookup(self, name: str) -> Optional[W_Object]:
        attr = 'w_' + name
        return getattr(self, attr, None)


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
        self.builtins.w_str = W_str._w
        self.builtins.w_None = W_void._w_singleton

    def dynamic_type(self, w_obj: W_Object) -> W_Type:
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

    def make_function(self, w_functype: W_FunctionType, w_code: W_CodeObject,
                      w_mod: W_Module) -> W_Function:
        """
        Create a function inside a module
        """
        w_func = W_Function(w_functype, w_code, w_mod.content)
        w_mod.add(w_code.name, w_func)
        return w_func

    def is_compatible_type(self, w_arg: W_Object, w_type: W_Type) -> bool:
        # XXX: this check is wrong: we should define better what it means to
        # be "compatible", but we don't have this notion yet
        return self.dynamic_type(w_arg) is w_type

    def call_function(self, w_func: W_Function, args_w: list[W_Object]) -> W_Object:
        w_functype = w_func.w_functype
        assert len(w_functype.argtypes_w) == len(args_w)
        for w_type, w_arg in zip(w_functype.argtypes_w, args_w):
            assert self.is_compatible_type(w_arg, w_type)
        #
        frame = Frame(self, w_func.w_code, w_func.globals)
        return frame.run(args_w)
