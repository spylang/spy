import py.path
import spy.ast
from spy.parser import Parser
from spy.irgen.typechecker import TypeChecker
from spy.irgen.modgen import ModuleGen
from spy.vm.vm import SPyVM
from spy.vm.module import W_Module


class IRGenerator:
    """
    Glue together all the various pieces which are necessary to convert SPy
    source code into an W_Module.

    By calling the appropriate methods, it is possible to run the pipeline
    only up to a certain point, which is useful to inspect and test the
    individual steps.
    """
    vm: SPyVM
    file_spy: py.path.local  # input file
    modname: str
    parser: Parser
    mod: spy.ast.Module
    t: TypeChecker
    modgen: ModuleGen
    w_mod: W_Module

    def __init__(self, vm: SPyVM, file_spy: py.path.local) -> None:
        self.vm = vm
        self.file_spy = file_spy
        # XXX this is good for now but should probably change in the future:
        # for now, we derive the modname only from the filename, but
        # eventually we need to add support for packages and submodules
        self.modname = file_spy.purebasename
        #
        self.parser = None  # type: ignore
        self.mod = None     # type: ignore
        self.t = None       # type: ignore
        self.modgen = None  # type: ignore
        self.w_mod = None   # type: ignore

    def make_w_mod(self) -> W_Module:
        self.parser = Parser.from_filename(str(self.file_spy))
        self.mod = self.parser.parse()
        self.t = TypeChecker(self.vm, self.mod)
        self.t.check_everything()
        self.modgen = ModuleGen(self.vm, self.t, self.modname, self.mod,
                                self.file_spy)
        self.w_mod = self.modgen.make_w_mod()
        return self.w_mod
