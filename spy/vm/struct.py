from typing import TYPE_CHECKING, Annotated, Any, Iterable, Optional

from spy.errors import WIP
from spy.fqn import FQN
from spy.vm.b import BUILTINS, TYPES, B
from spy.vm.builtin import IRTag, W_BuiltinFunc, builtin_method
from spy.vm.field import W_Field
from spy.vm.function import FuncParam, W_FuncType
from spy.vm.object import ClassBody, W_Object, W_Type
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.property import W_StaticMethod

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

OFFSETS_T = dict[str, int]


@TYPES.builtin_type("StructType")
class W_StructType(W_Type):
    size: int
    spy_key_is_valid: bool

    def define_from_classbody(self, vm: "SPyVM", body: ClassBody) -> None:
        # compute the layout of the struct and get the list of its fields
        struct_fields_w, size = calc_layout(body.fields_w)
        self.size = size

        # dict_w contains all the methods and properties
        dict_w: dict[str, W_Object] = {}

        # add an accessor for each field
        for w_struct_field in struct_fields_w:
            dict_w[w_struct_field.name] = w_struct_field

        # add the remaining methods
        for key, w_obj in body.dict_w.items():
            assert key not in dict_w, "need to think what to do"
            if key == "__make__":
                raise WIP("you cannot define your own __make__")
            dict_w[key] = w_obj

        # add '__make__' and optionally '__new__'
        w_make = self._create_w_make(vm, struct_fields_w)
        dict_w["__make__"] = W_StaticMethod(w_make)
        if "__new__" not in dict_w:
            dict_w["__new__"] = w_make

        # by default structs are value types and spy_key() returns a reasonable
        # key. However, if we define a custom __eq__ or __ne__, spy_key() is no longer
        # usable. In particular it means that we cannot pass such a struct as a
        # parameter of a @blue function.
        #
        # We need to think how to solve the problem. Probably we should introduce a
        # __key__ method.
        if "__eq__" in dict_w or "__ne__" in dict_w:
            self.spy_key_is_valid = False
        else:
            self.spy_key_is_valid = True

        super().define(W_Struct, dict_w)

    def _create_w_make(
        self, vm: "SPyVM", struct_fields_w: list["W_StructField"]
    ) -> W_BuiltinFunc:
        """
        Generate the '__make__' staticmethod.

        It's best explained via an example:

            @struct
            class Point:
                x: i32
                y: i32

                # __make__ is automatically generated and cannot be written manually
                @staticmethod
                def __make__(x: i32, y: i32) -> Point:
                    ...

                # if the use doesn't specify a __new__, by default we use __make__
                __new__ = __make__
        """
        STRUCT = Annotated[W_Struct, self]
        # functype
        params = [FuncParam(w_field.w_T, "simple") for w_field in struct_fields_w]
        w_functype = W_FuncType.new(params, w_restype=self)

        # impl
        def w_make_impl(vm: "SPyVM", *args_w: W_Object) -> STRUCT:
            assert len(args_w) == len(struct_fields_w)
            w_res = W_Struct(self)
            for w_arg, w_fld in zip(args_w, struct_fields_w, strict=True):
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

    def iterfields_w(self) -> Iterable["W_StructField"]:
        for w_obj in self.dict_w.values():
            if isinstance(w_obj, W_StructField):
                yield w_obj


def calc_layout(fields_w: dict[str, W_Field]) -> tuple[list["W_StructField"], int]:
    from spy.vm.modules.unsafe.misc import sizeof

    offset = 0
    struct_fields_w = []
    for name, w_field in fields_w.items():
        field_size = sizeof(w_field.w_T)
        # compute alignment
        offset = (offset + (field_size - 1)) & ~(field_size - 1)
        struct_fields_w.append(W_StructField(name, w_field.w_T, offset))
        offset += field_size
    size = offset
    return struct_fields_w, size


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
        if not self.w_structtype.spy_key_is_valid:
            # see the comment in W_StructType.define_from_classbody
            T = self.w_structtype.fqn.human_name
            raise WIP(
                f"type {T} cannot be cached because it defines __eq__ or __ne__",
            )
        values_key = [w_val.spy_key(vm) for w_val in self.values_w.values()]
        return ("struct", self.w_structtype.spy_key(vm)) + tuple(values_key)

    def spy_unwrap(self, vm: "SPyVM") -> Any:
        fqn = self.w_structtype.fqn

        # hack hack hack, as we don't have a better way to check whether w_T is a 'list'
        is_list = str(fqn).startswith("_list::list[")
        if is_list:
            return unwrap_list(vm, self)

        fields = {key: w_obj.spy_unwrap(vm) for key, w_obj in self.values_w.items()}
        return UnwrappedStruct(fqn, fields)

    def __repr__(self) -> str:
        fqn = self.w_structtype.fqn
        return f"<spy struct {fqn}({self.values_w})>"


@TYPES.builtin_type("StructField")
class W_StructField(W_Object):
    __spy_storage_category__ = "value"

    def __init__(self, name: str, w_T: W_Type, offset: int) -> None:
        self.name = name
        self.w_T = w_T
        self.offset = offset

    def spy_key(self, vm: "SPyVM") -> Any:
        return ("StructField", self.name, self.w_T.spy_key(vm), self.offset)

    def __repr__(self) -> str:
        n = self.name
        t = self.w_T.fqn.human_name
        return f"<spy struct field {n}: `{t}` (+{self.offset})>"

    @builtin_method("__get__", color="blue", kind="metafunc")
    @staticmethod
    def w_GET(vm: "SPyVM", wam_self: W_MetaArg, wam_struct: W_MetaArg) -> W_OpSpec:
        w_field = wam_self.w_blueval
        w_structtype = wam_struct.w_static_T
        assert isinstance(w_field, W_StructField)
        assert isinstance(w_structtype, W_StructType)

        name = w_field.name
        T = Annotated[W_Object, w_field.w_T]
        STRUCT = Annotated[W_Struct, w_structtype]
        irtag = IRTag("struct.getfield", name=name)

        @vm.register_builtin_func(w_structtype.fqn, f"__get_{name}__", irtag=irtag)
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
    _content: dict[str, Any]

    def __init__(self, fqn: FQN, content: dict[str, Any]) -> None:
        self.fqn = fqn
        self._content = content

    def spy_wrap(self, vm: "SPyVM") -> W_Struct:
        "This is needed for tests, to use structs as function arguments"
        w_structT = vm.lookup_global(self.fqn)
        assert isinstance(w_structT, W_StructType)
        struct_fields_w = w_structT.iterfields_w()
        assert set(self._content.keys()) == {w_f.name for w_f in struct_fields_w}
        w_struct = W_Struct(w_structT)
        w_struct.values_w = {key: vm.wrap(obj) for key, obj in self._content.items()}
        return w_struct

    def __getattr__(self, attr: str) -> Any:
        return self._content[attr]

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, UnwrappedStruct):
            return self.fqn == other.fqn and self._content == other._content
        elif isinstance(other, tuple):
            # this is to make tests easier: in this case, we just compare with
            # the fields
            return other == tuple(self._content.values())
        else:
            return NotImplemented

    def __ne__(self, other: Any) -> bool:
        return not (self == other)

    def __repr__(self) -> str:
        return f"<UnwrappedStruct {self.fqn}: {self._content}>"


def unwrap_list(vm: "SPyVM", w_list: W_Object) -> list[Any]:
    """
    Only useful in tests
    """
    items = []
    w_n = vm.call_w(B.w_len, [w_list], color="red")
    n = vm.unwrap_i32(w_n)
    for i in range(n):
        w_item = vm.getitem_w(w_list, vm.wrap(i), color="red")
        items.append(vm.unwrap(w_item))
    return items
