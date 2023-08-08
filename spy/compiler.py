import os
import py.path
import spy.ast
from spy.parser import Parser
from spy.irgen.typechecker import TypeChecker
from spy.irgen.modgen import ModuleGen
from spy.backend.c.cwriter import CModuleWriter
from spy.cbuild import ZigToolchain
from spy.vm.vm import SPyVM
from spy.vm.module import W_Module

DUMP_C = False
DUMP_WASM = False

class CompilerPipeline:
    """
    Glue together all the various pieces which are necessary to compile a SPy
    module.

    By calling the appropriate methods, it is possible to run the compiler
    only up to a certain point, which is useful to inspect and test the
    individual steps.
    """
    vm: SPyVM
    file_spy: py.path.local  # input file
    builddir: py.path.local
    #
    parser: Parser
    mod: spy.ast.Module
    t: TypeChecker
    modgen: ModuleGen
    w_mod: W_Module
    file_c: py.path.local    # output file
    file_wasm: py.path.local # output file

    def __init__(self, vm: SPyVM, file_spy: py.path.local, builddir: py.path.local) -> None:
        self.vm = vm
        self.file_spy = file_spy
        self.builddir = builddir
        #
        self.parser = None  # type: ignore
        self.mod = None     # type: ignore
        self.t = None       # type: ignore
        self.modgen = None  # type: ignore
        self.w_mod = None   # type: ignore
        #
        basename = file_spy.purebasename
        self.file_c = builddir.join(f'{basename}.c')
        self.file_wasm = builddir.join(f'{basename}.wasm')

    def parse(self) -> spy.ast.Module:
        assert self.parser is None, 'parse() already called'
        self.parser = Parser.from_filename(str(self.file_spy))
        self.mod = self.parser.parse()
        return self.mod

    def typecheck(self) -> spy.ast.Module:
        assert self.t is None, 'typecheck() already called'
        self.parse()
        self.t = TypeChecker(self.vm, self.mod)
        self.t.check_everything()
        return self.mod

    def irgen(self) -> W_Module:
        assert self.modgen is None, 'irgen() already called'
        self.typecheck()
        self.modgen = ModuleGen(self.vm, self.t, self.mod)
        self.w_mod = self.modgen.make_w_mod()
        return self.w_mod

    def cwrite(self) -> py.path.local:
        """
        Convert the W_Module into a .c file
        """
        self.irgen()
        self.cwriter = CModuleWriter(self.vm, self.w_mod,
                                     self.file_spy, self.file_c)
        self.cwriter.write_c_source()
        #
        if DUMP_C:
            print()
            print(f'---- {self.file_c} ----')
            print(self.file_c.read())
        #
        return self.file_c

    def cbuild(self) -> py.path.local:
        """
        Build the .c file into a .wasm file
        """
        file_c = self.cwrite()
        toolchain = ZigToolchain()
        exports = list(self.w_mod.content.values_w.keys())
        file_wasm = toolchain.c2wasm(file_c, self.file_wasm,
                                     exports=exports)
        #
        if DUMP_WASM:
            print()
            print(f'---- {self.file_wasm} ----')
            os.system(f'wasm2wat {file_wasm}')
        #
        return file_wasm
