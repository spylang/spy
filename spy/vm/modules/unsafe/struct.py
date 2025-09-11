from typing import TYPE_CHECKING
from spy.errors import WIP
from spy.vm.object import W_Object, W_Type, ClassBody
from spy.vm.field import W_Field
from . import UNSAFE
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

OFFSETS_T = dict[str, int]

@UNSAFE.builtin_type('StructType')
class W_StructType(W_Type):
    fields_w: dict[str, W_Field]
    offsets: OFFSETS_T
    size: int

    def define_from_classbody(self, body: ClassBody) -> None:
        super().define(W_Struct)
        self.fields_w = body.fields_w.copy()
        self.offsets, self.size = calc_layout(self.fields_w)
        if body.dict_w != {}:
            raise WIP('methods in structs')

    def repr_hints(self) -> list[str]:
        return super().repr_hints() + ['struct']

    def is_struct(self, vm: 'SPyVM') -> bool:
        return True


def calc_layout(fields_w: dict[str, W_Field]) -> tuple[OFFSETS_T, int]:
    from spy.vm.modules.unsafe.misc import sizeof
    offset = 0
    offsets = {}
    for name, w_field in fields_w.items():
        field_size = sizeof(w_field.w_T)
        # compute alignment
        offset = (offset + (field_size - 1)) & ~(field_size - 1)
        offsets[name] = offset
        offset += field_size
    size = offset
    return offsets, size


@UNSAFE.builtin_type('struct')
class W_Struct(W_Object):
    pass
