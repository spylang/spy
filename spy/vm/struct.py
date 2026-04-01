from typing import TYPE_CHECKING, Annotated, Any, Iterable, Optional

from spy import ast
from spy.analyze.scope import ScopeAnalyzer
from spy.errors import WIP, SPyError
from spy.fqn import FQN
from spy.location import Loc
from spy.vm.b import BUILTINS, TYPES, B
from spy.vm.builtin import W_BuiltinFunc, builtin_method
from spy.vm.field import W_Field
from spy.vm.function import FuncParam, W_ASTFunc, W_BuiltinFunc, W_FuncType
from spy.vm.irtag import IRTag
from spy.vm.modules.__spy__.interp_dict import W_InterpDict
from spy.vm.object import ClassBody, W_Object, W_Type
from spy.vm.opspec import W_MetaArg, W_OpSpec
from spy.vm.property import W_StaticMethod

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM


@TYPES.builtin_func(color="red")
def w__eq_ne_placeholder(vm: "SPyVM", w_a: W_Object, w_b: W_Object) -> None:
    """
    Temporary placeholder for struct's __eq__ and __ne__. See
    W_StructType.define_from_classbody.
    """
    raise SPyError("W_AssertionError", "_eq_ne_placeholder should never be called")


@TYPES.builtin_type("StructType")
class W_StructType(W_Type):
    size: int
    spy_key_is_valid: bool

    def define_from_classbody(self, vm: "SPyVM", body: ClassBody) -> None:
        """
        "Finalize" the definition of the struct type.

        The lazy/define distinction is needed because of @ModuleRegistry.struct_type:
        structs defined that way don't have a vm available immediately, so we need to
        split the logic in two:

          1. vm-indipendent logic is done inside lazy_define_from_classbody
          2. vm-dependent logic is done here

        In particular, we need a vm to create custom ASTFuncs for __eq__ and __ne__, and
        for registering those plus __make__ to the vm globals.
        """
        self.lazy_define_from_classbody(body)
        # add the __make__ to the globals
        w_meth = self.dict_w["__make__"]
        assert isinstance(w_meth, W_StaticMethod)
        w_make = w_meth.w_obj
        assert isinstance(w_make, W_BuiltinFunc)
        vm.add_global(w_make.fqn, w_make, irtag=IRTag("struct.make"))

        if self.spy_key_is_valid:
            assert self.dict_w["__eq__"] is TYPES.w__eq_ne_placeholder
            assert self.dict_w["__ne__"] is TYPES.w__eq_ne_placeholder
            self.dict_w["__eq__"] = w_eq = self._create_w_eq_ne("__eq__")
            self.dict_w["__ne__"] = w_ne = self._create_w_eq_ne("__ne__")
            vm.add_global(w_eq.fqn, w_eq)
            vm.add_global(w_ne.fqn, w_ne)

    def lazy_define_from_classbody(self, body: ClassBody) -> None:
        """
        Partially define the struct type.
        """
        # compute the layout of the struct and get the list of its fields
        if "__extra_fields__" in body.dict_w:
            w_extra = body.dict_w.pop("__extra_fields__")
            assert isinstance(w_extra, W_InterpDict)
            for name, (_, w_type) in w_extra.items_w.items():
                assert isinstance(w_type, W_Type)
                body.fields_w[name] = W_Field(name, w_type, body.loc)

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
        w_make = self._create_w_make(struct_fields_w)
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
            dict_w["__eq__"] = w__eq_ne_placeholder
            dict_w["__ne__"] = w__eq_ne_placeholder

        super().define(W_Struct, dict_w)

    def _create_w_make(self, struct_fields_w: list["W_StructField"]) -> W_BuiltinFunc:
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
        return w_make

    def _create_w_eq_ne(self, name: str) -> W_ASTFunc:
        """
        Auto-generate __eq__ or __ne__ as an ASTFunc for field-by-field comparison.

        def __eq__(a: Point, b: Point) -> bool:
            return a.x == b.x and a.y == b.y and ...

        def __ne__(a: Point, b: Point) -> bool:
            return not (a.x == b.x and a.y == b.y and ...)
        """
        fields_w = list(self.iterfields_w())
        func_loc = Loc.here()

        def cmp_field(w_field: W_StructField) -> ast.Expr:
            loc = w_field.loc
            a = ast.GetAttr(loc, ast.Name(loc, "a"), ast.StrConst(loc, w_field.name))
            b = ast.GetAttr(loc, ast.Name(loc, "b"), ast.StrConst(loc, w_field.name))
            return ast.CmpOp(Loc.here(), "==", a, b)

        if not fields_w:
            result: ast.Expr = ast.Constant(func_loc, True)
        else:
            result = cmp_field(fields_w[0])
            for w_field in fields_w[1:]:
                result = ast.And(w_field.loc, result, cmp_field(w_field))

        if name == "__eq__":
            stmt = ast.Return(func_loc, result)
        elif name == "__ne__":
            stmt = ast.Return(func_loc, ast.UnaryOp(Loc.here(), "not", result))
        else:
            assert False

        self_type = ast.FQNConst(func_loc, self.fqn)
        funcdef = ast.FuncDef(
            loc=func_loc,
            color="red",
            kind="plain",
            name=name,
            args=[
                ast.FuncArg(func_loc, "a", self_type, "simple"),
                ast.FuncArg(func_loc, "b", self_type, "simple"),
            ],
            return_type=ast.FQNConst(func_loc, B.w_bool.fqn),
            defaults=[],
            docstring=None,
            body=[stmt],
            decorators=[],
        )

        # create a fake module so that we can run ScopeAnalyzer
        module = ast.Module(
            loc=func_loc,
            filename="<generated>",
            docstring=None,
            decls=[ast.GlobalFuncDef(func_loc, funcdef)],
        )
        analyzer = ScopeAnalyzer(self.fqn.modname, module)
        analyzer.analyze()

        # create the actual W_ASTFunc object
        params = [FuncParam(self, "simple"), FuncParam(self, "simple")]
        w_functype = W_FuncType.new(params, w_restype=B.w_bool)
        fqn = self.fqn.join(name)
        return W_ASTFunc(w_functype, fqn, funcdef, closure=(), defaults_w=[])

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
        struct_fields_w.append(W_StructField(name, w_field.w_T, offset, w_field.loc))
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

        is_dict = str(fqn).startswith("_dict::dict[")
        if is_dict:
            return unwrap_dict(vm, self)

        fields = {key: w_obj.spy_unwrap(vm) for key, w_obj in self.values_w.items()}
        return UnwrappedStruct(fqn, fields)

    def __repr__(self) -> str:
        fqn = self.w_structtype.fqn
        return f"<spy struct {fqn}({self.values_w})>"


@TYPES.builtin_type("StructField")
class W_StructField(W_Object):
    __spy_storage_category__ = "value"

    def __init__(self, name: str, w_T: W_Type, offset: int, loc: Loc) -> None:
        self.name = name
        self.w_T = w_T
        self.offset = offset
        self.loc = loc

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


def unwrap_dict(vm: "SPyVM", w_dict: W_Object) -> dict[Any, Any]:
    """
    Only useful in tests
    """
    result: dict[Any, Any] = {}
    w_dict_T = vm.dynamic_type(w_dict)
    w_fastiter = vm.lookup_global(w_dict_T.fqn.join("__fastiter__"))
    w_it = vm.call_w(w_fastiter, [w_dict], color="red")
    w_it_T = vm.dynamic_type(w_it)
    w_continue_iteration = vm.lookup_global(w_it_T.fqn.join("__continue_iteration__"))
    is_continue = vm.call_w(w_continue_iteration, [w_it], color="red")
    w_next = vm.lookup_global(w_it_T.fqn.join("__next__"))
    w_it = vm.call_w(w_next, [w_it], color="red")

    while vm.unwrap_bool(is_continue):
        w_it_T = vm.dynamic_type(w_it)
        w_item_method = vm.lookup_global(w_it_T.fqn.join("__item__"))
        w_key = vm.call_w(w_item_method, [w_it], color="red")
        w_val = vm.getitem_w(w_dict, w_key, color="red")
        result[vm.unwrap(w_key)] = vm.unwrap(w_val)  # append key,value

        w_next = vm.lookup_global(w_it_T.fqn.join("__next__"))
        w_it = vm.call_w(w_next, [w_it], color="red")
        w_continue_iteration = vm.lookup_global(
            w_it_T.fqn.join("__continue_iteration__")
        )
        is_continue = vm.call_w(w_continue_iteration, [w_it], color="red")

    return result
