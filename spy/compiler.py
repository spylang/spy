from typing import Any, Literal
import spy.ast
from spy.parser import Parser
from spy.irgen.typechecker import TypeChecker
from spy.irgen.modgen import ModuleGen
from spy.backend.interp import InterpModuleWrapper
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
    srcfile: str
    parser: Parser
    mod: spy.ast.Module
    t: TypeChecker
    modgen: ModuleGen
    w_mod: W_Module

    def __init__(self, vm: SPyVM, backend: str, srcfile: str) -> None:
        self.vm = vm
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

    def compile(self, backend: Backend) -> Any:
        """
        Compile the W_Module into something which can be accessed and called by
        tests.

        Currently, the only support backend is 'interp', which is a fake
        backend: the IR code is not compiled and function are executed by the
        VM.
        """
        self.irgen()
        if backend == 'interp':
            interp_mod = InterpModuleWrapper(self.vm, self.w_mod)
            return interp_mod
        elif backend == 'C':
            raise NotImplementedError('WIP')
        else:
            assert False, f'Unknown backend: {backend}'
