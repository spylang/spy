import py.path
import spy.ast
from spy.parser import Parser
from spy.irgen.typechecker import TypeChecker
from spy.irgen.modgen import ModuleGen
from spy.vm.vm import SPyVM
from spy.vm.module import W_Module

def make_w_mod_from_file(vm: SPyVM, f: py.path.local) -> W_Module:
    """
    Glue together all the various pieces which are necessary to convert SPy
    source code into an W_Module.
    """
    parser = Parser.from_filename(str(f))
    mod = parser.parse()
    t = TypeChecker(vm, mod)
    t.check_everything()
    modname = f.purebasename
    modgen = ModuleGen(vm, t, modname, mod, f)
    return modgen.make_w_mod()
