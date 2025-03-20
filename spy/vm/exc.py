from typing import TYPE_CHECKING, Annotated
from spy.errfmt import ErrorFormatter, Level, Annotation
from spy.vm.opimpl import W_OpImpl, W_OpArg
from spy.vm.builtin import builtin_func, builtin_method
from spy.vm.primitive import W_Bool
from spy.vm.object import W_Object, W_Type, Member
from spy.vm.str import W_Str
from spy.vm.b import BUILTINS

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

@BUILTINS.builtin_type('Exception')
class W_Exception(W_Object):
    message: str

    def __init__(self, message: str) -> None:
        self.message = message


    @builtin_method('__NEW__', color='blue')
    @staticmethod
    def w_NEW(vm: 'SPyVM', wop_cls: W_OpArg, *args_wop: W_OpArg) -> W_OpImpl:
        # we cannot use the default __new__ because we want to pass w_cls
        w_cls = wop_cls.w_blueval
        assert isinstance(w_cls, W_Type)
        fqn = w_cls.fqn
        T = Annotated[W_Exception, w_cls]

        # the whole "raise Exception(...)" is a bit of a hack at the moment:
        # the C backend can raise only BLUE exceptions, so here we make sure
        # that Exception("...") is blue
        @builtin_func(fqn, '__new__', color='blue')
        def w_new(vm: 'SPyVM', w_cls: W_Type, w_message: W_Str) -> T:
            pyclass = w_cls.pyclass
            assert issubclass(pyclass, W_Exception)
            message = vm.unwrap_str(w_message)
            return pyclass(message)
        return W_OpImpl(w_new, [wop_cls] + list(args_wop))


    @builtin_method('__EQ__', color='blue')
    @staticmethod
    def w_EQ(vm: 'SPyVM', wop_a: W_OpArg, wop_b: W_OpArg) -> W_OpImpl:
        from spy.vm.opimpl import W_OpImpl

        w_atype = wop_a.w_static_type
        w_btype = wop_b.w_static_type

        # If different exception types, return null implementation
        if w_atype is not w_btype:
            return W_OpImpl.NULL

        @builtin_func(w_atype.fqn)
        def w_eq(vm: 'SPyVM', w_exc1: W_Exception, w_exc2: W_Exception) -> W_Bool:
            # Compare the message fields
            return vm.eq(w_exc1.w_message, w_exc2.w_message)

        return W_OpImpl(w_eq)

    @builtin_method('__NE__', color='blue')
    @staticmethod
    def w_NE(vm: 'SPyVM', wop_a: W_OpArg, wop_b: W_OpArg) -> W_OpImpl:
        from spy.vm.opimpl import W_OpImpl

        w_atype = wop_a.w_static_type
        w_btype = wop_b.w_static_type

        # If different exception types, return null implementation
        if w_atype is not w_btype:
            return W_OpImpl.NULL

        @builtin_func(w_atype.fqn)
        def w_ne(vm: 'SPyVM', w_exc1: W_Exception, w_exc2: W_Exception) -> W_Bool:
            # Compare the message fields and negate the result
            return vm.ne(w_exc1.w_message, w_exc2.w_message)

        return W_OpImpl(w_ne)

    @builtin_method('__new__', color='blue')
    @staticmethod
    def w_spy_new(vm: 'SPyVM', w_message: W_Str) -> 'W_Exception':
        return W_Exception(w_message)

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        return f'{cls}({self.w_message})'

    def spy_str(self, vm: 'SPyVM') -> str:
        """
        Ad-hoc stringify logic. Eventually, we should have __STR__

        Return an interp-level str formatted like this:
            Exception: hello
        """
        w_exc_type = vm.dynamic_type(self)
        t = w_exc_type.fqn.symbol_name
        m = self.message
        return f'{t}: {m}'


@BUILTINS.builtin_type('ValueError')
class W_ValueError(W_Exception):
    pass

@BUILTINS.builtin_type('TypeError')
class W_TypeError(W_Exception):
    pass

@BUILTINS.builtin_type('IndexError')
class W_IndexError(W_Exception):
    pass


@BUILTINS.builtin_type('StaticError')
class W_StaticError(W_Exception):
    pass
