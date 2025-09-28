from typing import TYPE_CHECKING, Annotated, Any
from spy.errors import WIP
from spy.vm.object import W_Object, W_Type, ClassBody
from spy.vm.field import W_Field
from spy.vm.function import W_FuncType, FuncParam
from spy.vm.builtin import W_BuiltinFunc
from spy.vm.opspec import W_MetaArg, W_OpSpec
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
        if '__new__' not in self.dict_w:
            self.dict_w['__new__'] = self._make_w_new()

    def _make_w_new(self):
        STRUCT = Annotated[W_Struct, self]
        # functype
        params = [
            FuncParam(w_field.w_T, 'simple')
            for w_field in self.fields_w.values()
        ]
        w_functype = W_FuncType.new(params, w_restype=self)

        # impl
        def w_new_impl(vm: 'SPyVM', *args_w: W_Object) -> STRUCT:
            assert len(args_w) == len(self.fields_w)
            w_res = W_Struct(self)
            for w_arg, w_fld in zip(args_w, self.fields_w.values(), strict=True):
                w_res.values_w[w_fld.name] = w_arg
            return w_res

        # make the __new__
        fqn = self.fqn.join('__new__')
        return W_BuiltinFunc(w_functype, fqn, w_new_impl)

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
    """
    Struct object allocated ON THE STACK.

    For now, structs-by-value are intentionally limited in functionality: in
    particular, they are immutable and you cannot get their address to make a
    pointer to them.

    This is intentional and by design, because it greatly simplifies the
    implementation in the interpreter. We might want to change the rules in
    the future.

    The interp-level represenation of structs on heap and stack is
    very different:

      - heap: gc_alloc() allocs a bunch of bytes and the fields are
        stored in the mem.

      - stack: we store the fields as a dictionary. That's the main reason why
        we cannot get its address, because we don't have any backing memory
        underlying.

    If we want to relax this limitation in the future, we will probably need
    to have a stack pointer in the WASM memory, and reserve some stack space
    in ast ASTFrame. But then we would also need to think about memory safety
    and lifetimes.
    """
    __spy_storage_category__ = 'value'
    w_structtype: W_StructType

    def __init__(self, w_structtype: W_StructType) -> None:
        self.w_structtype = w_structtype
        self.values_w = {}

    def spy_get_w_type(self, vm: 'SPyVM') -> W_Type:
        return self.w_structtype

    def spy_key(self, vm: 'SPyVM') -> Any:
        values_key = [w_val.spy_key(vm) for w_val in self.values_w.values()]
        return ('struct', self.w_structtype.spy_key(vm)) + tuple(values_key)
