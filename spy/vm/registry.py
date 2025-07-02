from typing import Callable, TYPE_CHECKING, Any, Type
from types import FunctionType
from spy.ast import Color, FuncKind
from spy.fqn import FQN, QUALIFIERS

if TYPE_CHECKING:
    from spy.vm.object import W_Object
    from spy.vm.function import W_BuiltinFunc

class ModuleRegistry:
    """
    Keep track of all the objects which belong to a certain module.

    At startup, the `vm` will create a W_Module out of it.
    """
    fqn: FQN
    content: list[tuple[FQN, 'W_Object']]

    def __init__(self, modname: str) -> None:
        self.fqn = FQN(modname)
        self.content = []

    def __repr__(self) -> str:
        return f"<ModuleRegistry '{self.fqn}'>"

    if TYPE_CHECKING:
        def __getattr__(self, attr: str) -> Any:
            """
            Workaround for mypy blindness.

            When we do X.add('foo', ...), it becomes available as X.w_foo, but
            mypy obviously doesn't know. This is a big problem in particular
            for the B (builtins) module, since we use B.w_i32, B.w_object,
            etc. everywhere.

            By using this fake __getattr__, mypy will never complain about
            missing attributes on ModuleRegistry (which is a bit suboptimal,
            but well...)
            """

    def add(self, attr: str, w_obj: 'W_Object') -> None:
        fqn = self.fqn.join(attr)
        attr = f'w_{attr}'
        assert not hasattr(self, attr)
        setattr(self, attr, w_obj)
        self.content.append((fqn, w_obj))

    def builtin_type(self,
                     typename: str,
                     qualifiers: QUALIFIERS = None,
                     *,
                     lazy_definition: bool = False,
                     ) -> Callable:
        """
        Register a type on the module.

        In practice:
            @MOD.spytype('Foo')
            class W_Foo('W_Object'):
                ...

        is equivalent to:
            @spytype('Foo')
            class W_Foo('W_Object'):
                ...
            MOD.add('Foo', W_Foo._w)
        """
        from spy.vm.builtin import builtin_type
        def decorator(pyclass: Type['W_Object']) -> Type['W_Object']:
            bt_deco = builtin_type(self.fqn, typename, qualifiers,
                                   lazy_definition=lazy_definition)
            W_class = bt_deco(pyclass)
            self.add(typename, W_class._w)
            return W_class
        return decorator

    def builtin_func(self,
                     pyfunc_or_funcname: Callable|str|None = None,
                     qualifiers: QUALIFIERS = None,
                     *,
                     color: Color = 'red',
                     kind: FuncKind = 'plain',
                     ) -> Any:
        """
        Register a builtin function on the module. We support three
        different syntaxes:

        # funcname is automatically set to 'foo'
        @MOD.builtin_func
        def w_foo(): ...

        @MOD.builtin_func('myfuncname')
        def w_foo(): ...

        @MOD.builtin_func(color='...')
        def foo(): ...

        'qualifiers' is allowed only if you also explicitly specify
        'funcname'.
        """
        from spy.vm.builtin import builtin_func
        if isinstance(pyfunc_or_funcname, FunctionType):
            pyfunc = pyfunc_or_funcname
            funcname = None
            assert qualifiers is None
        elif isinstance(pyfunc_or_funcname, str):
            pyfunc = None
            funcname = pyfunc_or_funcname
        else:
            assert pyfunc_or_funcname is None
            pyfunc = None
            funcname = None
            assert qualifiers is None

        def decorator(pyfunc: Callable) -> 'W_BuiltinFunc':
            namespace = self.fqn
            # apply the @builtin_func decorator to pyfunc
            w_func = builtin_func(
                namespace=namespace,
                funcname=funcname,
                qualifiers=qualifiers,
                color=color,
                kind=kind,
            )(pyfunc)
            setattr(self, f'w_{w_func.fqn.symbol_name}', w_func)
            self.content.append((w_func.fqn, w_func))
            return w_func

        if pyfunc is None:
            return decorator
        else:
            return decorator(pyfunc)
