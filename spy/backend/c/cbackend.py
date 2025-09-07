from typing import Optional
import py.path
from spy.backend.c.cmodwriter import CModule, CModuleWriter
from spy.backend.c.cffiwriter import CFFIWriter
from spy.build.config import BuildConfig
from spy.build.ninja import NinjaWriter
from spy.build.cffi import cffi_build
from spy.vm.vm import SPyVM
from spy.vm.cell import W_Cell
from spy.vm.object import W_Object
from spy.vm.function import W_ASTFunc
from spy.vm.primitive import W_I32
from spy.vm.modules.unsafe.ptr import W_PtrType
from spy.util import highlight_C_maybe


class CBackend:
    """
    Convert SPy modules into C files
    """
    vm: SPyVM
    outname: str
    config: BuildConfig
    build_dir: py.path.local
    dump_c: bool
    cffi: CFFIWriter
    ninja: Optional[NinjaWriter]
    c_modules: dict[str, CModule]
    cfiles: list[py.path.local]
    build_script: Optional[py.path.local]

    def __init__(
            self,
            vm: SPyVM,
            outname: str,
            config: BuildConfig,
            build_dir: py.path.local,
            *,
            dump_c: bool
    ) -> None:
        self.vm = vm
        self.outname = outname
        self.config = config
        self.build_dir = build_dir
        self.build_dir.join('src').ensure(dir=True)
        self.dump_c = dump_c
        #
        self.cffi = CFFIWriter(outname, config, build_dir)
        self.ninja = None
        self.c_modules = {}
        self.cfiles = [] # generated C files
        self.build_script = None

    def init_c_modules(self) -> None:
        """
        Create one C module for each .spy file

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
        for modname, w_mod in self.vm.modules_w.items():
            spyfile = None
            hfile = None
            cfile = None
            if w_mod.filepath is not None:
                # a non-builtin module
                spyfile = py.path.local(w_mod.filepath)
                basename = spyfile.purebasename
                hfile = bdir.join('src', f'{basename}.h')
                cfile = bdir.join('src', f'{basename}.c')
            c_mod = CModule(
                modname = modname,
                is_builtin = w_mod.is_builtin(),
                spyfile = spyfile,
                hfile = hfile,
                cfile = cfile,
                content = [],
            )
            self.c_modules[modname] = c_mod

        # fill the content of C modules
        for fqn, w_obj in self.vm.globals_w.items():
            if fqn.is_module():
                # don't put the module in its own content
                continue
            modname = fqn.modname
            self.c_modules[modname].content.append((fqn, w_obj))
        self.c_modules['ptrs_builtins'] = self.make_ptrs_builtins()

    def make_ptrs_builtins(self) -> CModule:
        """
        ptrs_builtins is a special module which contains all the
        specialized ptr types to builtins (e.g. ptr[i32]).
        """
        # find all the unsafe::ptr to a builtin
        def is_ptr_to_builtin(w_obj: W_Object) -> bool:
            return (
                isinstance(w_obj, W_PtrType) and
                w_obj.w_itemtype.fqn.modname == 'builtins'
            )
        return CModule(
            modname = 'ptrs_builtins',
            is_builtin = False,
            spyfile = None,
            hfile = self.build_dir.join('src', 'ptrs_builtins.h'),
            cfile = None,
            content = [
                (fqn, w_obj)
                for fqn, w_obj in self.vm.globals_w.items()
                if is_ptr_to_builtin(w_obj)
            ]
        )

    def cwrite(self) -> None:
        """
        Convert all non-builtins modules into .c files
        """
        self.init_c_modules()
        for modname, c_mod in self.c_modules.items():
            if c_mod.is_builtin:
                continue
            cwriter = CModuleWriter(self.vm, c_mod, self.cffi)
            cwriter.write_c_source()
            # c_mod.cfile can be None for modules which emit only .h
            # (e.g. ptrs_builtins)
            if c_mod.cfile is not None:
                self.cfiles.append(c_mod.cfile)
                if self.dump_c:
                    print()
                    print(f'---- {c_mod.cfile} ----')
                    print(highlight_C_maybe(c_mod.cfile.read()))

    def write_build_script(self) -> None:
        assert self.cfiles != [], 'call .cwrite() first'
        wasm_exports = []
        if self.config.target == 'wasi' and self.config.kind == 'lib':
            wasm_exports = self.get_wasm_exports()

        if self.config.kind == 'py-cffi':
            assert wasm_exports == []
            self.build_script = self.cffi.write(self.cfiles)
        else:
            self.ninja = NinjaWriter(self.config, self.build_dir)
            self.ninja.write(self.outname, self.cfiles,
                             wasm_exports=wasm_exports)
            self.build_script = self.build_dir.join('build.ninja')


    def build(self) -> py.path.local:
        if self.config.kind == 'py-cffi':
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
            if c_mod.is_builtin:
                continue
            wasm_exports += [
                fqn.c_name
                for fqn, w_obj in c_mod.content
                if (isinstance(w_obj, W_ASTFunc) and w_obj.color == 'red' or
                    isinstance(w_obj, W_Cell))
            ]
        return wasm_exports
