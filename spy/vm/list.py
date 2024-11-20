from typing import (TYPE_CHECKING, Any, Optional, Type, ClassVar,
                    TypeVar, Generic, Annotated)
from spy.vm.b import B
from spy.vm.primitive import W_I32, W_Bool, W_Dynamic, W_Void
from spy.vm.object import (W_Object, W_Type)
from spy.vm.builtin import builtin_func, builtin_type
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.opimpl import W_OpImpl, W_OpArg


class Meta_W_List(type):
    """
    Some magic to be able to do e.g. W_List[W_MyClass].

    W_List[] works only if the result was prebuilt by calling
    W_List.make_prebuilt(W_MyClass).

    It is guaranteed that make_list_type will use the prebuilt class, in
    case it exists, i.e.:

        make_list_type(vm, B.w_i32) is vm.wrap(W_List[W_I32])
    """
    CACHE: ClassVar[dict[Type[W_Object], 'Type[W_List]']] = {}

    def __getitem__(self, itemcls: Type[W_Object]) -> 'Type[W_List]':
        if itemcls in self.CACHE:
            return self.CACHE[itemcls]
        else:
            n = itemcls.__name__
            msg = (f"W_List[{n}] is not available. Make sure to build it by "
                   f"calling W_List.make_prebuilt({n}) at import time")
            raise ValueError(msg)

    def make_prebuilt(self, itemcls: Type[W_Object]) -> None:
        assert issubclass(itemcls, W_Object)
        if itemcls not in self.CACHE:
            W_MyList = _make_W_List(itemcls._w)
            self.CACHE[itemcls] = W_MyList

T = TypeVar('T', bound='W_Object')

@B.builtin_type('list')
class W_List(W_Object, Generic[T], metaclass=Meta_W_List):
    """
    The 'list' type.

    It has two purposes:

      - it's the base type for all lists

      - by implementing meta_op_GETITEM, it can be used to create
       _specialized_ list types, e.g. `list[i32]`.

    In other words, `list[i32]` inherits from `list`.

    The specialized types are created by calling the builtin make_list_type:
    see its docstring for details.
    """
    items_w: list[T]
    __spy_storage_category__ = 'reference'

    def __init__(self, items_w: list[T]) -> None:
        raise NotImplementedError

    @classmethod
    def make_prebuilt(cls, itemcls: Type[W_Object]) -> None:
        """
        Just a shortcut to reach Meta_W_List more easily
        """
        type(cls).make_prebuilt(cls, itemcls)

    @staticmethod
    def meta_op_GETITEM(vm: 'SPyVM', wop_obj: 'W_OpArg',
                        wop_i: 'W_OpArg') -> 'W_OpImpl':
        from spy.vm.opimpl import W_OpImpl
        return W_OpImpl(w_make_list_type)



@builtin_func('__spy__', color='blue')
def w_make_list_type(vm: 'SPyVM', w_list: W_Object, w_T: W_Type) -> W_Type:
    """
    Create a concrete W_List class specialized for W_Type.

    Given a type T, it is always safe to call make_list_type(T) multiple
    types, and it is guaranteed to get always the same type.

    It is worth noting that to achieve that, we have two layers of caching:

      - if we have a prebuilt list type, just use that
      - for other types, we rely on the fact that `make_list_type` is blue.
    """
    assert w_list is W_List._w
    if w_T.pyclass in Meta_W_List.CACHE:
        w_list_type = vm.wrap(Meta_W_List.CACHE[w_T.pyclass])
    else:
        pyclass = _make_W_List(w_T)
        w_list_type = vm.wrap(pyclass)
    assert isinstance(w_list_type, W_Type)
    return w_list_type


def _make_W_List(w_T: W_Type) -> Type[W_List]:
    """
    DON'T CALL THIS DIRECTLY!
    You should call make_list_type instead, which knows how to deal with
    prebuilt types.
    """
    from spy.vm.opimpl import W_OpImpl

    T = Annotated[W_Object, w_T]

    @builtin_type('builtins', 'list', [w_T.fqn])
    class W_MyList(W_List):
        __qualname__ = f'W_List[{w_T.pyclass.__name__}]' # e.g. W_List[W_I32]
        items_w: list[W_Object]

        def __init__(self, items_w: list[W_Object]) -> None:
            # XXX typecheck?
            self.items_w = items_w

        def __repr__(self) -> str:
            cls = self.__class__.__name__
            return f'{cls}({self.items_w})'

        def spy_unwrap(self, vm: 'SPyVM') -> list[Any]:
            return [vm.unwrap(w_item) for w_item in self.items_w]

        @staticmethod
        def op_GETITEM(vm: 'SPyVM', wop_obj: 'W_OpArg',
                       wop_i: 'W_OpArg') -> W_OpImpl:
            @builtin_func(W_MyList.type_fqn)
            def w_getitem(vm: 'SPyVM', w_list: W_MyList, w_i: W_I32) -> T:
                i = vm.unwrap_i32(w_i)
                # XXX bound check?
                return w_list.items_w[i]
            return W_OpImpl(w_getitem)

        @staticmethod
        def op_SETITEM(vm: 'SPyVM', wop_obj: 'W_OpArg', wop_i: 'W_OpArg',
                       wop_v: 'W_OpArg') -> W_OpImpl:
            from spy.vm.b import B

            @builtin_func(W_MyList.type_fqn)
            def w_setitem(vm: 'SPyVM', w_list: W_MyList, w_i: W_I32,
                          w_v: T) -> W_Void:
                i = vm.unwrap_i32(w_i)
                # XXX bound check?
                w_list.items_w[i] = w_v
                return B.w_None
            return W_OpImpl(w_setitem)

        @staticmethod
        def op_EQ(vm: 'SPyVM', wop_l: 'W_OpArg', wop_r: 'W_OpArg') -> W_OpImpl:
            from spy.vm.b import B
            w_ltype = wop_l.w_static_type
            w_rtype = wop_r.w_static_type
            assert w_ltype.pyclass is W_MyList

            @builtin_func(W_MyList.type_fqn)
            def w_eq(vm: 'SPyVM', w_l1: W_MyList, w_l2: W_MyList) -> W_Bool:
                items1_w = w_l1.items_w
                items2_w = w_l2.items_w
                if len(items1_w) != len(items2_w):
                    return B.w_False
                for w_1, w_2 in zip(items1_w, items2_w):
                    if vm.is_False(vm.eq(w_1, w_2)):
                        return B.w_False
                return B.w_True

            if w_ltype is w_rtype:
                return W_OpImpl(w_eq)
            else:
                return W_OpImpl.NULL

    W_MyList.__name__ = W_MyList.__qualname__
    return W_MyList
