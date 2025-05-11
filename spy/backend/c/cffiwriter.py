import os
import textwrap
import py.path
from spy.build.config import BuildConfig, CompilerConfig
from spy.vm.vm import SPyVM
from spy.textbuilder import TextBuilder, Color


class CFFIWriter:
    """
    Generate a script cffi-build.py which contains all the necessary info
    to build cffi wrappers around a set of SPy modules
    """
    config: BuildConfig
    build_dir: py.path.local

    def __init__(
            self,
            config: BuildConfig,
            build_dir: py.path.local
    ) -> None:
        self.config = config
        self.build_dir = build_dir
        self.tb = TextBuilder()
        self.init_cffi_build()

    def init_cffi_build(self):
        self.tb.wb("""
        from cffi import FFI
        """)
        #
        self.tb.wl()
        self.tb.wl('CDEF = """')
        self.tb_cdef = self.tb.make_nested_builder()
        self.tb.wl('"""')
        self.tb.wl()
        self.tb.wl('SRC = """')
        self.tb_src = self.tb.make_nested_builder()
        self.tb.wl('"""')
        self.tb.wl()

    def finalize_cffi_build(
            self,
            modname: str,
            cfiles: list[py.path.local]
    ) -> None:
        srcdir = self.build_dir.join('src')
        comp = CompilerConfig(self.config)

        SOURCES = [str(f) for f in cfiles]
        CFLAGS = comp.cflags + [
            f'-I{srcdir}'
        ]
        LDFLAGS = comp.ldflags

        self.tb.wb(f"""
        ffibuilder = FFI()
        ffibuilder.cdef(CDEF)
        ffibuilder.set_source(
            "{modname}",
            SRC,
            sources={SOURCES},
            extra_compile_args={CFLAGS},
            extra_link_args={LDFLAGS},
        )

        if __name__ == "__main__":
            sofile = ffibuilder.compile(verbose=False)
            print(sofile)
        """)

    def write(self, modname: str, cfiles: list[py.path.local]) -> py.path.local:
        assert self.config.kind == 'py:cffi'
        self.finalize_cffi_build(modname, cfiles)

        self.cffi_dir = self.build_dir.join('cffi')
        self.cffi_dir.ensure(dir=True)
        outfile = self.cffi_dir.join('cffi-build.py')
        outfile.write(self.tb.build())
        return outfile
