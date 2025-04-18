from typing import Any
import py.path
import spy.ast
from spy.fqn import FQN
from spy.parser import Parser
from spy.analyze.scope import ScopeAnalyzer
from spy.vm.modframe import ModFrame

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
    symtable = scopes.by_module()
    fqn = FQN(modname)
    modframe = ModFrame(vm, fqn, symtable, mod)
    w_mod = modframe.run()
    return w_mod
