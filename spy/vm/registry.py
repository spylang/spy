from dataclasses import dataclass, field
from types import FunctionType
from typing import TYPE_CHECKING, Any, Callable, Optional, Type

import py.path

from spy.ast import Color, FuncKind
from spy.fqn import FQN, QUALIFIERS
from spy.location import Loc
from spy.vm.irtag import IRTag

if TYPE_CHECKING:
    from spy.vm.function import W_BuiltinFunc
    from spy.vm.object import W_Object, W_Type
    from spy.vm.struct import W_StructType
    from spy.vm.vm import SPyVM


@dataclass
class CModuleBuildInfo:
    """
    C-build metadata for an out-of-tree builtin module.

    Collected by SPyVM and consumed by the C backend to:
      - add -I flags so the generated C code can #include the module's headers;
      - emit #include directives for the module's public header in generated code;
      - link the module's .a archives into the final binary.

    Archive layout mirrors spy/libspy/build/:
        <build_dir>/<target>/lib<name>.a

    The C backend selects the right subdirectory based on the build target, so
    the module only needs to declare the root and the archive filenames.
    """

    # Each entry is (build_dir, archive_name). Archives are resolved as
    # build_dir/<target>/<archive_name>. Multiple entries are used when the
    # module bundles several independent C libraries, each with its own build
    # tree (e.g. glue code + vendored third-party library).
    archive_specs: list[tuple[py.path.local, str]] = field(default_factory=list)
    # Absolute paths to directories to add as -I flags when compiling.
    include_dirs: list[py.path.local] = field(default_factory=list)
    # Public header files to #include in generated C that calls this module.
    # Paths are absolute; the C backend emits them verbatim.
    headers: list[py.path.local] = field(default_factory=list)


class ModuleRegistry:
    """
    Keep track of all the objects which belong to a certain module.

    At startup, the `vm` will create a W_Module out of it.
    """

    fqn: FQN
    content: list[tuple[FQN, "W_Object", IRTag]]
    loc: Loc
    # .a archives (wasm32-wasi-musl) to bundle with libspy when this module is
    # loaded in interpreted mode. Typically the module's own glue code plus any
    # third-party library it wraps.
    wasm_archives: list[py.path.local]
    # C-build metadata consumed by the C backend. None for in-tree builtins
    # (their headers ship with libspy and their symbols live in libspy.a).
    build_info: Optional[CModuleBuildInfo]

    def __init__(self, modname: str) -> None:
        self.fqn = FQN(modname)
        self.content = []
        self.loc = Loc.here(-2)
        self.wasm_archives = []
        self.build_info = None

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

    def add(
        self,
        attr: str,
        w_obj: "W_Object",
        *,
        irtag: IRTag = IRTag.Empty,
    ) -> None:
        fqn = self.fqn.join(attr)
        attr = f"w_{attr}"
        assert not hasattr(self, attr)
        setattr(self, attr, w_obj)
        self.content.append((fqn, w_obj, irtag))

    def builtin_type(
        self,
        typename: str,
        qualifiers: QUALIFIERS = None,
        *,
        lazy_definition: bool = False,
        W_MetaClass: Optional[Type["W_Type"]] = None,
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

        def decorator(pyclass: Type["W_Object"]) -> Type["W_Object"]:
            bt_deco = builtin_type(
                self.fqn,
                typename,
                qualifiers,
                lazy_definition=lazy_definition,
                W_MetaClass=W_MetaClass,
            )
            W_class = bt_deco(pyclass)
            self.add(typename, W_class._w)
            return W_class

        return decorator

    def struct_type(
        self,
        typename: str,
        fields: list[tuple[str, "W_Type"]],
        *,
        builtin: bool = False,
    ) -> "W_StructType":
        """
        Register a struct type on the module.

        fields is a list of (name, w_type) pairs, e.g.:
            [("x", B.w_i32), ("y", B.w_i32)]

        If builtin is True, the C backend does NOT generate the struct definition: it is
        expected to be provided by libspy.
        """
        from spy.location import Loc
        from spy.vm.field import W_Field
        from spy.vm.function import W_BuiltinFunc
        from spy.vm.object import ClassBody
        from spy.vm.property import W_StaticMethod
        from spy.vm.struct import W_StructType

        # Use the call site of struct_type as the loc for all fields and the body.
        loc = Loc.here(-2)
        fqn = self.fqn.join(typename)
        body = ClassBody(
            loc=loc,
            fields_w={name: W_Field(name, w_T, loc) for name, w_T in fields},
            dict_w={},
        )
        w_st = W_StructType.declare(fqn)
        w_st.lazy_define_from_classbody(body)

        # lazy_define_from_classbody creates the __make__ but does NOT add it to the
        # globals. Instead, we add it to the module contents so that it will be
        # automatically added to the "right" vm when calling make_module.
        w_meth = w_st.dict_w["__make__"]
        assert isinstance(w_meth, W_StaticMethod)
        w_make = w_meth.w_obj
        assert isinstance(w_make, W_BuiltinFunc)

        # add the struct type and the __make__ function to the registry
        if builtin:
            irtag = IRTag("struct.builtin")
        else:
            irtag = IRTag.Empty
        self.add(typename, w_st, irtag=irtag)
        self.content.append((w_make.fqn, w_make, IRTag("struct.make")))

        return w_st

    def builtin_func(
        self,
        pyfunc_or_funcname: Callable | str | None = None,
        qualifiers: QUALIFIERS = None,
        *,
        color: Color = "red",
        kind: FuncKind = "plain",
        hidden: bool = False,
        is_pure: bool = False,
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
        from spy.vm.builtin import make_builtin_func

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

        def decorator(pyfunc: Callable) -> "W_BuiltinFunc":
            w_func = make_builtin_func(
                pyfunc,
                namespace=self.fqn,
                funcname=funcname,
                qualifiers=qualifiers,
                color=color,
                kind=kind,
                is_pure=is_pure,
            )
            setattr(self, f"w_{w_func.fqn.symbol_name}", w_func)
            if not hidden:
                self.content.append((w_func.fqn, w_func, IRTag.Empty))
            return w_func

        if pyfunc is None:
            return decorator
        else:
            return decorator(pyfunc)
