from typing import Optional, TYPE_CHECKING, Union
from collections import deque
import py.path
from spy import ast
from spy.fqn import FQN
from spy.parser import Parser
from spy.analyze.scope import ScopeAnalyzer
from spy.vm.modframe import ModFrame

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.module import W_Module

MODULE = Union[py.path.local, 'W_Module', None]

class ImportAnalizyer:
    # XXX explain

    def __init__(self, vm: 'SPyVM', modname: str) -> None:
        self.vm = vm
        self.queue = deque([modname])
        self.mods = {}

    def analyze(self) -> None:
        while self.queue:
            modname = self.queue.popleft()

            if modname in self.mods:
                # we are already visiting this module, nothing to do
                pass

            elif modname in self.vm.modules_w:
                # the module is already fully imported, record it
                w_mod = self.vm.modules_w[modname]
                self.mods[modname] = w_mod

            elif f := self.get_filename(modname):
                # new module to visit: parse it and recursively visit it. This
                # might append more mods to self.queue.
                parser = Parser.from_filename(str(f))
                mod = parser.parse()
                self.mods[modname] = mod
                self.visit(mod)

            else:
                # we couldn't find .spy for this modname
                self.mods[modname] = None

    def get_filename(self, modname: str) -> Optional[py.path.local]:
        # XXX for now we assume that we find the module as a single file in
        # the only vm.path entry. Eventually we will need a proper import
        # mechanism and support for packages
        assert self.vm.path, 'vm.path not set'
        f = py.path.local(self.vm.path[0]).join(f'{modname}.spy')
        # XXX maybe THIS is the right place where to raise SPyImportError?
        if f.exists():
            return f
        else:
            return None

    def import_all(self) -> None:
        assert not self.queue, 'call .analyze() first'
        all_mods = reversed(self.mods.items()) # XXX explain
        for modname, mod in all_mods:
            if isinstance(mod, ast.Module):
                self.import_one(modname, mod)


    def import_one(self, modname: str, mod: ast.Module) -> None:
        scopes = ScopeAnalyzer(self.vm, modname, mod)
        scopes.analyze()
        symtable = scopes.by_module()
        fqn = FQN(modname)
        modframe = ModFrame(self.vm, fqn, symtable, mod)
        w_mod = modframe.run()
        self.vm.modules_w[modname] = w_mod

    def pp(self) -> None:
        from spy.vm.module import W_Module
        for modname, mod in self.mods.items():
            if isinstance(mod, ast.Module):
                print(f'{modname} -> {mod.filename}')
            elif isinstance(mod, W_Module):
                print(f'{modname} -> <builtin>')
            elif mod is None:
                print(f'{modname} -> ImportError')
            else:
                assert False

    # ===========================================================
    # visitor pattern to recurively find all "import" statements

    def visit(self, mod: ast.Module) -> None:
        mod.visit('visit', self)

    def visit_Import(self, imp: ast.Import) -> None:
        self.queue.append(imp.fqn.modname)

    # ===========================================================
