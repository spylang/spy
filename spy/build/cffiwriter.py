import os
import textwrap
import py.path
from spy.build.config import BuildConfig, CompilerConfig
from spy.vm.vm import SPyVM
from spy.textbuilder import TextBuilder, Color
from spy.backend.c.cffidef import CFFIDef

# XXX fix this!
# XXX: for now we hardcode it for 'add.spy', but of course we need to do it
# properly
CDEF = """
int32_t add(int32_t x, int32_t y);
"""
SRC = """
#include "add.h"
#define add spy_add$add
"""


class CFFIWriter:
    config: BuildConfig
    build_dir: py.path.local

    def __init__(
            self,
            cffidef: CFFIDef,
            config: BuildConfig,
            build_dir: py.path.local
    ) -> None:
        assert config.kind == 'py:cffi'
        self.cffidef = cffidef
        self.config = config
        self.build_dir = build_dir
        self.cffi_dir = self.build_dir.join('cffi')
        self.cffi_dir.ensure(dir=True)

    def write(self, modname: str, cfiles: list[py.path.local]) -> py.path.local:
        comp = CompilerConfig(self.config)
        outfile = self.cffi_dir.join('cffi-build.py')

        cffi_cdef = self.cffidef.tb_cdef.build()
        cffi_cdef = textwrap.indent(cffi_cdef, " " * 8)

        cffi_src = self.cffidef.tb_src.build()
        cffi_src = textwrap.indent(cffi_src, " " * 8)

        SOURCES = [str(f) for f in cfiles]
        CFLAGS = comp.cflags

        srcdir = self.build_dir.join('src')
        CFLAGS += [
            f'-I{srcdir}'
        ]

        LDFLAGS = comp.ldflags
        tb = TextBuilder()
        tb.wb(f"""
        import os
        from pathlib import Path
        from cffi import FFI

        ffibuilder = FFI()
        ffibuilder.cdef('''
        {cffi_cdef}
        ''')
        src = '''
        {cffi_src}
        '''

        ffibuilder.set_source(
            "{modname}",
            src,
            sources={SOURCES},
            extra_compile_args={CFLAGS},
            extra_link_args={LDFLAGS},
        )

        if __name__ == "__main__":
            ffibuilder.compile(verbose=True)
        """)
        outfile.write(tb.build())
        return outfile
