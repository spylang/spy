from typing import Any
import py.path
import spy.ast
from spy.parser import Parser
from spy.irgen.scope import ScopeAnalyzer
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
    modname = f.purebasename
    scopes = ScopeAnalyzer(vm, modname, mod)
    scopes.analyze()
    modgen = ModuleGen(vm, scopes, modname, mod, f)
    return modgen.make_w_mod()
