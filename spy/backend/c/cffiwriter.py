from pathlib import Path

from spy.backend.c.context import Context
from spy.build.config import BuildConfig, CompilerConfig
from spy.fqn import FQN
from spy.textbuilder import TextBuilder
from spy.vm.function import W_ASTFunc


class CFFIWriter:
    """
    Generate a script *-cffi-build.py which contains all the necessary info
    to build cffi wrappers around a set of SPy modules.

    Imagine to compile `foo.spy`, which contains two functions `add` and
    `sub`. CFFIWriter produces more or less the following:

        ### foo.py
        import _foo
        add = _foo.lib.spy_foo_add
        sub = _foo.lib.spy_foo_sub

        ### _foo-cffi-build.py
        [...]
        ffibuilder.cdef('''
            int spy_foo_add(int x, int y);
            int spy_foo_sub(int x, int y);
        ''')
        src = '''
            #define spy_foo_add spy_foo$add
            #define spy_foo_sub spy_foo$sub
        '''

        ffibuilder.set_source(
            "_add",
            src,
            extra_sources=[...],        # list of all necessary .c files
            extra_compile_args=[...],   # cflags
            extra_link_args=[...],      # ldflags
            ...
        )

        if __name__ == '__main__':
            ffibuilder.compile()

    To generate `_add.so`, you can manually call `_add-cffi-build.py`, or
    integrate it inside a broader python packaging solution, e.g. by using the
    CFFI "Setuptools integration" as described here:
    https://cffi.readthedocs.io/en/latest/cdef.html
    """

    modname: str
    config: BuildConfig
    build_dir: Path
    tb_py: TextBuilder
    tb_build: TextBuilder
    tb_cdef: TextBuilder
    tb_src: TextBuilder

    def __init__(self, modname: str, config: BuildConfig, build_dir: Path) -> None:
        self.modname = modname
        self.config = config
        self.build_dir = build_dir
        self.tb_py = TextBuilder()  # {modname}.py
        self.tb_build = TextBuilder()  # _{modname-cffi-build}.py
        self.init_py()
        self.init_cffi_build()

    def init_py(self) -> None:
        self.tb_py.wb(f"""
        import _{self.modname}
        """)

    def init_cffi_build(self) -> None:
        tb = self.tb_build
        tb.wb("""
        from cffi import FFI
        """)
        #
        tb.wl()
        tb.wl('CDEF = """')
        self.tb_cdef = tb.make_nested_builder()
        tb.wl('"""')
        tb.wl()
        tb.wl('SRC = """')
        self.tb_src = tb.make_nested_builder()
        tb.wl('"""')
        tb.wl()

    def finalize_cffi_build(self, cfiles: list[Path]) -> None:
        srcdir = self.build_dir / "src"
        comp = CompilerConfig(self.config)

        SOURCES = [str(f) for f in cfiles]
        CFLAGS = comp.cflags + [f"-I{srcdir}"]
        LDFLAGS = comp.ldflags

        self.tb_build.wb(f"""
        ffibuilder = FFI()
        ffibuilder.cdef(CDEF)
        ffibuilder.set_source(
            "_{self.modname}",
            SRC,
            sources={SOURCES},
            extra_compile_args={CFLAGS},
            extra_link_args={LDFLAGS},
        )

        if __name__ == "__main__":
            sofile = ffibuilder.compile(verbose=False)
            print(sofile)
        """)

    def write(self, cfiles: list[Path]) -> Path:
        assert self.config.kind == "py-cffi"
        self.finalize_cffi_build(cfiles)

        self.cffi_dir = self.build_dir / "cffi"
        self.cffi_dir.mkdir(exist_ok=True)

        pyfile = self.cffi_dir / f"{self.modname}.py"
        pyfile.write_text(self.tb_py.build())

        build_script = self.cffi_dir / f"_{self.modname}-cffi-build.py"
        build_script.write_text(self.tb_build.build())
        return build_script

    def emit_include(self, header_name: str) -> None:
        self.tb_src.wb(f"""
        #include "{header_name}"
        """)

    def emit_func(self, ctx: Context, fqn: FQN, w_func: W_ASTFunc) -> None:
        """
        Emit CFFI declaration for the function
        """
        # fqn.c_name is something like 'spy_test$add'. The workaround is to
        # use a different name in cdef, and a #define in src, like this:
        #     ffibuilder.cdef("void spy_test_add(...)");
        #     src = "#define spy_test_add spy_test$add"
        real_name = fqn.c_name
        cdef_name = real_name.replace("$", "_")
        c_func = ctx.c_function(cdef_name, w_func)
        self.tb_cdef.wl(c_func.decl() + ";")
        self.tb_src.wl(f"#define {cdef_name} {real_name}")
        #
        # XXX explain
        py_name = fqn.symbol_name
        self.tb_py.wl(f"{py_name} = _{self.modname}.lib.{cdef_name}")
