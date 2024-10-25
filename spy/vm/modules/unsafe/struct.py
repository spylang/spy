from typing import TYPE_CHECKING, Any, no_type_check, Optional, Type, ClassVar
from dataclasses import dataclass
import fixedint
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type, W_I32, W_Void
from spy.vm.sig import spy_builtin
from spy.vm.opimpl import W_OpImpl, W_Value
from . import UNSAFE
from .ptr import read_ptr, write_ptr
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.opimpl import W_OpImpl, W_Value


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
        return f"<spy type struct '{self.name}'>"

    def is_struct(self) -> bool:
        return True


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
    pass


def make_struct_type(vm: 'SPyVM', name: str,
                     fields: dict[str, W_Type]) -> W_Type:
    size, layout = calc_layout(fields)

    class W_MyStruct(W_Struct):
        pass

    W_MyStruct.__name__ = W_MyStruct.__qualname__ = f'W_{name}'
    w_struct_type = W_StructType(name, W_MyStruct, fields)
    W_MyStruct._w = w_struct_type # poor's man @spytype
    return w_struct_type
