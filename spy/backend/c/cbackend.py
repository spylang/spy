from graphlib import TopologicalSorter
from typing import Optional

import py.path

from spy.backend.c.cffiwriter import CFFIWriter
from spy.backend.c.cmodwriter import CModule, CModuleWriter
from spy.backend.c.cstructwriter import CStructDefs, CStructWriter
from spy.build.build_info import BuildInfo
from spy.build.cffi import cffi_build
from spy.build.config import BuildConfig
from spy.build.ninja import NinjaWriter
from spy.fqn import FQN
from spy.highlight import highlight_src
from spy.vm.cell import W_Cell
from spy.vm.function import W_ASTFunc
from spy.vm.modules.unsafe.ptr import W_MemLocType
from spy.vm.object import W_Object, W_Type
from spy.vm.primitive import W_I32
from spy.vm.struct import W_StructType
from spy.vm.vm import SPyVM


class CBackend:
    """
    Convert SPy modules into C files
    """

    vm: SPyVM
    main_modname: str
    outname: str
    config: BuildConfig
    build_dir: py.path.local
    dump_c: bool
    cffi: CFFIWriter
    ninja: Optional[NinjaWriter]
    c_structdefs: dict[str, CStructDefs]
    c_modules: dict[str, CModule]
    cfiles: list[py.path.local]
    build_script: Optional[py.path.local]

    def __init__(
        self,
        vm: SPyVM,
        main_modname: str,
        config: BuildConfig,
        build_dir: py.path.local,
        *,
        dump_c: bool,
    ) -> None:
        self.vm = vm
        self.main_modname = main_modname
        self.outname = main_modname
        self.config = config
        self.build_dir = build_dir
        self.build_dir.join("src").ensure(dir=True)
        self.dump_c = dump_c
        self.cffi = CFFIWriter(main_modname, config, build_dir)
        self.ninja = None
        self.c_structdefs = {}
        self.c_modules = {}
        self.cfiles = []  # generated C files
        self.build_script = None

    def split_fqns(self) -> None:
        """
        Split the global FQNs into multiple CModule and CStructDefs, which
        will later be written to disk.

        Generally speaking, we try to create a .c file for each .spy file.

        The ultimate goal of the C backend is to emit all the FQNs which were
        created during init and redshift. In theory, we could emit all of them
        into a single .c file and call it a day.

        However, in order to make debugging and development easier, we try to
        split them in a sensible way. In particular, we group them by their
        FQN.modname.

        Note that this is only VERY loosely relaed with the content of
        W_Modules. In particular, consider this case:

            # aaa.spy
            def foo() -> i32:
                return 42

            # bbb.spy
            import aaa
            bar = foo

        At startup the VM creates a function `aaa::foo`, which is present in
        both the dict of W_Module('aaa') and W_Module('bbb').

        But in the C backend we care only about the FQN, so `foo` will be
        emitted ONLY inside "aaa.c".

        "bbb.c" does not need it at all, because "bbb.bar" is a blue variable
        and thus all the references to it has been already redshifted away
        into an FQNConst("aaa::foo").
        """
        bdir = self.build_dir
        # create a CModule for each non-builtin SPy module
        for modname, w_mod in self.vm.modules_w.items():
            if w_mod.is_builtin():
                continue
            assert w_mod.filepath is not None
            spyfile = py.path.local(w_mod.filepath)
            basename = spyfile.purebasename
            hfile = bdir.join("src", f"{basename}.h")
            cfile = bdir.join("src", f"{basename}.c")
            c_mod = CModule(
                modname=modname,
                spyfile=spyfile,
                hfile=hfile,
                cfile=cfile,
                content=[],
            )
            self.c_modules[modname] = c_mod

        # We need to emit .h files with the struct defs.  For now we create a single
        # "structdefs.h" file with ALL the structs, topologically sorted to ensure that
        # is struct B has a field (by value) of type struct A, we emit A before B.
        #
        # See test_importing::test_circular_type_ref for an example of that.
        #
        # Eventually, we want to split structdefs into multiple files (to
        # avoid recompiling everything at every change), but this will be
        # non-obvious. It will require to:
        #   1. maintain a graph of struct dependencies
        #   2. identify the set of Strongly Connected Components (SCC)
        #   3. ensure that structs in each SCC is in topological order
        #   4. emit one .h for each SCC (or maybe group multiple SCC by
        #      modname, but keep in mind that in case of circular deps it will
        #      be impossible to guarantee the correspondance fqn.modname <=>
        #      modname.h)
        structdefs: list[tuple[FQN, W_Type]] = []

        # Put each FQN into the corresponding CModule or structdefs
        for fqn, w_obj in self.vm.globals_w.items():
            # ignore W_Modules
            if fqn.is_module():
                continue
            # ignore w_objs belonging to builtin modules, unless they are
            # ptr/ref types or struct types (which need C definitions)
            modname = fqn.modname
            w_mod = self.vm.modules_w[modname]
            if w_mod.filepath is None and not isinstance(
                w_obj, (W_MemLocType, W_StructType)
            ):
                continue

            if isinstance(w_obj, W_Type):
                structdefs.append((fqn, w_obj))
            else:
                self.c_modules[modname].content.append((fqn, w_obj))

        structdefs = self.topo_sort_structdefs(structdefs)
        self.c_structdefs["globals"] = CStructDefs(
            hfile=bdir.join("src", "spy_structdefs.h"),
            content=structdefs,
        )

    def cwrite(self) -> None:
        """
        Convert all non-builtins modules into .c files
        """
        self.vm.linearize_all()
        self.split_fqns()

        # Emit structdefs.h
        for c_structdefs in self.c_structdefs.values():
            cstructwriter = CStructWriter(self.vm, c_structdefs, self.cffi)
            cstructwriter.write_c_source()
            if self.dump_c:
                print()
                print(f"---- {c_structdefs.hfile} ----")
                print(highlight_src("C", c_structdefs.hfile.read()))  # type: ignore

        # Emit regular C modules
        for c_mod in self.c_modules.values():
            is_main_mod = c_mod.modname == self.main_modname
            cwriter = CModuleWriter(self.vm, c_mod, is_main_mod, self.cffi)
            cwriter.write_c_source()
            self.cfiles.append(c_mod.cfile)
            if self.dump_c:
                print()
                print(f"---- {c_mod.cfile} ----")
                print(highlight_src("C", c_mod.cfile.read()))  # type: ignore

    def get_merged_build_info(self) -> BuildInfo:
        """
        Call each module's build_info(target, build_type) and merge results
        into a single BuildInfo for the current config.
        """
        target = self.config.target
        build_type = self.config.build_type
        merged = BuildInfo()
        for build_info_fn in self.vm.build_info_funcs.values():
            info = build_info_fn(target, build_type)
            merged.include_dirs.extend(info.include_dirs)
            merged.archives.extend(info.archives)
            merged.cflags.extend(info.cflags)
            merged.ldflags.extend(info.ldflags)
        return merged

    def write_build_script(self) -> None:
        assert self.cfiles != [], "call .cwrite() first"
        wasm_exports = []
        if self.config.target == "wasi" and self.config.kind == "lib":
            wasm_exports = self.get_wasm_exports()

        extra = self.get_merged_build_info()
        if self.config.kind == "py-cffi":
            assert wasm_exports == []
            self.build_script = self.cffi.write(self.cfiles)
        else:
            self.ninja = NinjaWriter(self.config, self.build_dir)
            self.ninja.write(
                self.outname,
                self.cfiles,
                wasm_exports=wasm_exports,
                extra_include_dirs=extra.include_dirs,
                extra_archives=extra.archives,
                extra_cflags=extra.cflags,
                extra_ldflags=extra.ldflags,
            )
            self.build_script = self.build_dir.join("build.ninja")

    def build(self) -> py.path.local:
        if self.config.kind == "py-cffi":
            assert self.build_script is not None
            return cffi_build(self.build_script)
        else:
            assert self.ninja is not None
            return self.ninja.build()

    def get_wasm_exports(self) -> list[str]:
        # this is a bit of ad-hoc logic but it's probably good enough. For now
        # we export:
        #    1. functions
        #    2. red variables (who are stored inside a W_Cell)
        wasm_exports = []
        for modname, c_mod in self.c_modules.items():
            wasm_exports += [
                fqn.c_name
                for fqn, w_obj in c_mod.content
                if (
                    isinstance(w_obj, W_ASTFunc)
                    and w_obj.color == "red"
                    and not w_obj.is_force_inline
                    or isinstance(w_obj, W_Cell)
                )
            ]

        # common wasm exports
        libspy_exports = ["spy_str_alloc"]
        wasm_exports.extend(libspy_exports)

        return wasm_exports

    def get_type_deps(self, fqn: FQN) -> list[FQN]:
        """
        Return the FQNs of the types which `fqn` depends on, i.e. which need
        to be fully defined before `fqn` itself can be defined in C.

        A struct depends on the struct types of its by-value fields. Pointer
        and ref fields are NOT dependencies: a forward declaration of the
        pointee is enough, which is what makes mutually recursive types via
        pointers work.
        """
        w_type = self.vm.lookup_global(fqn)
        if isinstance(w_type, W_MemLocType):
            # A ptr/ref type emits `typedef struct PTR { T *p; ...} PTR;` into
            # the forward-decl section: it needs T's own typedef to appear
            # first.
            return [w_type.w_itemT.fqn]
        if not isinstance(w_type, W_StructType) or not w_type.is_defined():
            return []
        deps: list[FQN] = []
        seen: set[FQN] = set()
        for field in w_type.iterfields_w():
            w_fieldT = field.w_T
            if not isinstance(w_fieldT, W_StructType):
                continue
            dep_fqn = w_fieldT.fqn
            if dep_fqn != fqn and dep_fqn not in seen:
                seen.add(dep_fqn)
                deps.append(dep_fqn)
        return deps

    def topo_sort_structdefs(
        self, content: list[tuple[FQN, W_Type]]
    ) -> list[tuple[FQN, W_Type]]:
        all_types: dict[FQN, W_Type] = dict(content)
        ts: TopologicalSorter[FQN] = TopologicalSorter()
        for fqn in all_types:
            deps = [d for d in self.get_type_deps(fqn) if d in all_types]
            ts.add(fqn, *deps)
        return [(fqn, all_types[fqn]) for fqn in ts.static_order()]
