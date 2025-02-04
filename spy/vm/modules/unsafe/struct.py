from typing import TYPE_CHECKING, Any, Optional, Type, ClassVar
from dataclasses import dataclass
import fixedint
from spy.fqn import FQN
from spy.vm.function import W_Func
from spy.vm.primitive import W_I32, W_Void
from spy.vm.b import B
from spy.vm.object import W_Object, W_Type, ClassBody, FIELDS_T
from spy.vm.builtin import builtin_func
from spy.vm.opimpl import W_OpImpl, W_OpArg
from . import UNSAFE
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.opimpl import W_OpImpl, W_OpArg

OFFSETS_T = dict[str, int]

@UNSAFE.builtin_type('StructType')
class W_StructType(W_Type):
    fields: FIELDS_T
    offsets: OFFSETS_T
    size: int

    def define_from_classbody(self, body: ClassBody) -> None:
        super().define(W_Struct)
        self.fields = body.fields
        self.offsets, self.size = calc_layout(body.fields)
        assert body.methods == {}

    def __repr__(self) -> str:
        if self.is_defined():
            fw = ''
        else:
            fw = 'fwdecl '
        return f"<spy {fw}type '{self.fqn}' (struct)>"

    def is_struct(self, vm: 'SPyVM') -> bool:
        return True


def calc_layout(fields: FIELDS_T) -> tuple[OFFSETS_T, int]:
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


@UNSAFE.builtin_type('struct')
class W_Struct(W_Object):
    pass
