from typing import TYPE_CHECKING, Annotated, Any, Optional
from spy.errors import WIP
from spy.fqn import FQN
from spy.vm.b import TYPES, BUILTINS
from spy.vm.object import W_Object, W_Type, ClassBody
from spy.vm.field import W_Field
from spy.vm.function import W_FuncType, FuncParam
from spy.vm.builtin import W_BuiltinFunc, builtin_method, IRTag
from spy.vm.property import W_StaticMethod
from spy.vm.opspec import W_MetaArg, W_OpSpec
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

OFFSETS_T = dict[str, int]

@TYPES.builtin_type("StructType")
class W_StructType(W_Type):
    fields_w: dict[str, W_Field]
    offsets: OFFSETS_T
    size: int

    def define_from_classbody(self, vm: "SPyVM", body: ClassBody) -> None:
        super().define(W_Struct)
        self.fields_w = body.fields_w.copy()
        self.offsets, self.size = calc_layout(self.fields_w)

        for key, w_obj in body.dict_w.items():
            assert key not in self.dict_w, "need to think what to do"
            if key == "__make__":
                raise WIP("you cannot define your own __make__")
            self.dict_w[key] = w_obj

        # add a '__make__' staticmethod to create a struct by specifying all
        # the fields
        w_make = self._create_w_make(vm)
        self.dict_w["__make__"] = W_StaticMethod(w_make)

        # if the user didn't provide a '__new__', let's put a default one
        # which is just an alias to '__make__',
        if "__new__" not in self.dict_w:
            self.dict_w["__new__"] = w_make

    def _create_w_make(self, vm: "SPyVM") -> W_BuiltinFunc:
        STRUCT = Annotated[W_Struct, self]
        # functype
        params = [
            FuncParam(w_field.w_T, "simple")
            for w_field in self.fields_w.values()
        ]
        w_functype = W_FuncType.new(params, w_restype=self)

        # impl
        def w_make_impl(vm: "SPyVM", *args_w: W_Object) -> STRUCT:
            assert len(args_w) == len(self.fields_w)
            w_res = W_Struct(self)
            for w_arg, w_fld in zip(args_w, self.fields_w.values(), strict=True):
                w_res.values_w[w_fld.name] = w_arg
            return w_res

        # create the actual function object
        fqn = self.fqn.join("__make__")
        w_make = W_BuiltinFunc(w_functype, fqn, w_make_impl)
        vm.add_global(fqn, w_make, irtag=IRTag("struct.make"))
        return w_make

    def repr_hints(self) -> list[str]:
        return super().repr_hints() + ["struct"]

    def is_struct(self, vm: "SPyVM") -> bool:
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


@BUILTINS.builtin_type("struct")
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

    Note that this is only a limitation of the SPy VM. The C backend uses C
    structs, so taking-the-address will work out of the box.
    """
    __spy_storage_category__ = "value"
    w_structtype: W_StructType
    values_w: dict[str, W_Object]

    def __init__(
        self,
        w_structtype: W_StructType,
        values_w: Optional[dict[str, W_Object]] = None,
    ) -> None:
        self.w_structtype = w_structtype
        if values_w is None:
            self.values_w = {}
        else:
            self.values_w = values_w

    def spy_get_w_type(self, vm: "SPyVM") -> W_Type:
        return self.w_structtype

    def spy_key(self, vm: "SPyVM") -> Any:
        values_key = [w_val.spy_key(vm) for w_val in self.values_w.values()]
        return ("struct", self.w_structtype.spy_key(vm)) + tuple(values_key)

    def spy_unwrap(self, vm: "SPyVM") -> "UnwrappedStruct":
        fqn = self.w_structtype.fqn
        fields = {
            key: w_obj.spy_unwrap(vm)
            for key, w_obj in self.values_w.items()
        }
        return UnwrappedStruct(fqn, fields)

    def __repr__(self) -> str:
        fqn = self.w_structtype.fqn
        return f"<spy struct {fqn}({self.values_w})>"

    @builtin_method("__getattribute__", color="blue", kind="metafunc")
    @staticmethod
    def w_GETATTRIBUTE(vm: "SPyVM", wam_struct: W_MetaArg,
                       wam_name: W_MetaArg) -> W_OpSpec:
        w_structtype = wam_struct.w_static_T
        assert isinstance(w_structtype, W_StructType)
        name = wam_name.blue_unwrap_str(vm)
        if name not in w_structtype.fields_w:
            return W_OpSpec.NULL

        w_field = w_structtype.fields_w[name]
        T = Annotated[W_Object, w_field.w_T]
        STRUCT = Annotated[W_Struct, w_structtype]
        irtag = IRTag("struct.getfield", name=name)

        @vm.register_builtin_func(w_structtype.fqn, f"__get_{name}__",
                                  irtag=irtag)
        def w_get(vm: "SPyVM", w_struct: STRUCT) -> T:
            return w_struct.values_w[name]

        return W_OpSpec(w_get, [wam_struct])


class UnwrappedStruct:
    """
    Return value of vm.unwrap(w_some_struct). Mostly useful for tests.

    The logic to convert WASM values into UnwrappedStruct is in
    spy.tests.wasm_wrapper.WasmFuncWrapper.to_py_result.

    NOTE: the WASM version works only for flat structs with simple types. This
    is good enough for most tests.
    """
    fqn: FQN
    _fields: dict[str, Any]

    def __init__(self, fqn: FQN, fields: dict[str, Any]) -> None:
        self.fqn = fqn
        self._fields = fields

    def spy_wrap(self, vm: "SPyVM") -> W_Struct:
        "This is needed for tests, to use structs as function arguments"
        w_structT = vm.lookup_global(self.fqn)
        assert isinstance(w_structT, W_StructType)
        assert set(self._fields.keys()) == set(w_structT.fields_w.keys())
        w_struct = W_Struct(w_structT)
        w_struct.values_w = {
            key: vm.wrap(obj)
            for key, obj in self._fields.items()
        }
        return w_struct

    def __getattr__(self, attr: str) -> Any:
        return self._fields[attr]

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, UnwrappedStruct):
            return self.fqn == other.fqn and self._fields == other._fields
        elif isinstance(other, tuple):
            # this is to make tests easier: in this case, we just compare with
            # the fields
            return other == tuple(self._fields.values())
        else:
            return NotImplemented

    def __ne__(self, other: Any) -> bool:
        return not (self == other)

    def __repr__(self) -> str:
        return f"<UnwrappedStruct {self.fqn}: {self._fields}>"
