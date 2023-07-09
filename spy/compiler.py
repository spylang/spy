from typing import Any, Literal
from py.path import LocalPath
import spy.ast
from spy.parser import Parser
from spy.irgen.typechecker import TypeChecker
from spy.irgen.modgen import ModuleGen
from spy.backend.c.builder import CModuleBuilder
from spy.vm.vm import SPyVM
from spy.vm.module import W_Module

Backend = Literal['interp', 'C']

class CompilerPipeline:
    """
    Glue together all the various pieces which are necessary to compile a SPy
    module.

    By calling the appropriate methods, it is possible to run the compiler
    only up to a certain point, which is useful to inspect and test the
    individual steps.
    """
    vm: SPyVM
    srcfile: LocalPath
    builddir: LocalPath
    parser: Parser
    mod: spy.ast.Module
    t: TypeChecker
    modgen: ModuleGen
    w_mod: W_Module

    def __init__(self, vm: SPyVM, srcfile: LocalPath, builddir: LocalPath) -> None:
        self.vm = vm
        self.builddir = builddir
        self.srcfile = srcfile
        self.parser = None  # type: ignore
        self.mod = None     # type: ignore
        self.t = None       # type: ignore
        self.modgen = None  # type: ignore
        self.w_mod = None   # type: ignore

    def parse(self) -> spy.ast.Module:
        assert self.parser is None, 'parse() already called'
        self.parser = Parser.from_filename(str(self.srcfile))
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

    def cwrite(self):
        """
        Convert the W_Module into a .c file
        """
        self.irgen()
        self.cmod = CModuleBuilder(self.vm, self.w_mod, self.builddir)

    def cbuild(self):
        """
        Build the .c file into a .wasm file
        """
        self.cwrite()
        return self.cmod.build()
