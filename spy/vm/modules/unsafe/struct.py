from typing import TYPE_CHECKING, Any, no_type_check, Optional, Type, ClassVar
from dataclasses import dataclass
from spy.vm.object import W_Object, W_Type
from spy.vm.sig import spy_builtin
from spy.vm.opimpl import W_OpImpl, W_Value
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.opimpl import W_OpImpl, W_Value


@dataclass(repr=False)
class W_StructType(W_Type):
    fields: dict[str, W_Type]
    offsets: dict[str, int]
    size: int

    def __init__(self, name: str, pyclass: Type[W_Object],
                 fields: dict[str, W_Type]) -> None:
        super().__init__(name, pyclass)
        self.fields = fields
        self.offsets, self.size = calc_layout(fields)

    def __repr__(self) -> str:
        fields = ', '.join(self.fields)
        return f"<spy struct '{self.name}' ({fields})>"


def calc_layout(fields):
    from spy.vm.modules.unsafe.misc import sizeof

    offset = 0
    offsets = {}
    for field, w_type in fields.items():
        field_size = sizeof(w_type)
        # compute alignment
        offset = (offset + (field_size - 1)) & ~(field_size - 1)
        offsets[field] = offset
        offset += field_size
    size = offset
    return offsets, size


# XXX note that we don't call @spytype, because it's annoying to pass a custom
# metaclass. But it's fine for now because we don't need/want many
# functionalities: in particolar, we don't want to *instantiate* a struct: we
# just want to have a w_type to describe the fields, to pass to gc_alloc
class W_Struct(W_Object):

    def op_SETATTR(vm: 'SPyVM', wv_obj: W_Value, wv_attr: W_Value,
                   wv_v: W_Value) -> W_OpImpl:
        w_st = wv_obj.w_static_type
        attr = wv_attr.blue_unwrap_str(vm)
        assert isinstance(w_st, W_StructType)
        if attr not in w_st.fields:
            XXX
            # raise AttributeError
        return W_OpImpl.NULL



def make_struct_type(vm: 'SPyVM', name: str,
                     fields: dict[str, W_Type]) -> W_Type:
    size, layout = calc_layout(fields)

    class W_MyStruct(W_Struct):
        pass


    W_MyStruct.__name__ = W_MyStruct.__qualname__ = f'W_{name}'
    w_struct_type = W_StructType(name, W_MyStruct, fields)
    W_MyStruct._w = w_struct_type # poor's man @spytype
    return w_struct_type
