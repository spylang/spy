from typing import Optional, TYPE_CHECKING, Union
from collections import deque
import py.path
from spy import ast
from spy.fqn import FQN
from spy.parser import Parser
from spy.analyze.scope import ScopeAnalyzer
from spy.vm.modframe import ModFrame
from spy.textbuilder import ColorFormatter

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
    from spy.vm.module import W_Module

MODULE = Union[ast.Module, 'W_Module', None]


class ImportAnalizyer:
    """
    The set of modules needed and loaded by a SPy program is statically
    determined ahead of time.

    This is very different than Python where `import` is a statement which can
    trigger dynamic loading of a new module. In SPy, `import` is just a
    declaration which makes avaiable in the current module an entity which has
    already been loaded.

    NOTE: eventually, we might want to slightly tweak the rules to allow
    "true" dynamic loading also in SPy, but for now we support only
    fully-static loading.

    The set of modules to load is determined by statically looking at all the
    `import` statements present from the root module, and recursively visiting
    all the modules found in that way, INCLUDING the `import`s which are not
    top-level.

    This basicaly creates a tree of imports. E.g.:

        # main.spy
        import aaa
        import bbb

        # aaa.spy
        import a1
        def foo():
            import a2

        # bbb.spy
        import aaa
        import b1
        import b2


    This gives us an import tree which looks like that:

    +-- main
        +-- aaa
        |   +-- a1
        |   +-- a2
        +-- bbb
            +-- aaa
            +-- b1
            +-- b2

    The import order is determined by doing a *depth-first, post-order
    traversal of the tree, with memoization*. In the example above, it
    corresponds to:

    - a1
    - a2
    - aaa
    - b1
    - b2
    - bbb
    - main

    This more or less corresponds to what happens normally in Python when all
    the import statements are at top-level and there are no circular
    dependencies.

    Circular dependencies are currently not supported, but will be in the
    future.
    """
    def __init__(self, vm: 'SPyVM', modname: str) -> None:
        self.vm = vm
        self.queue = deque([modname])
        self.mods: dict[str, MODULE] = {}

    def getmod(self, modname: str) -> ast.Module:
        mod = self.mods[modname]
        assert isinstance(mod, ast.Module)
        return mod

    def parse_all(self) -> None:
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

    def analyze_scopes(self, modname: str) -> ScopeAnalyzer:
        assert self.mods, 'call .parse_all() first'
        mod = self.getmod(modname)
        scopes = ScopeAnalyzer(self.vm, modname, mod)
        scopes.analyze()
        return scopes

    def get_import_list(self) -> list[str]:
        # XXX: the following logic is broken and doesn't do what the class
        # docstring says
        return list(reversed(self.mods))

    def import_all(self) -> None:
        assert self.mods, 'call .parse_all() first'
        import_list = self.get_import_list()
        for modname in import_list:
            mod = self.mods[modname]
            if isinstance(mod, ast.Module):
                self.import_one(modname, mod)

    def import_one(self, modname: str, mod: ast.Module) -> None:
        scopes = self.analyze_scopes(modname)
        symtable = scopes.by_module()
        fqn = FQN(modname)
        modframe = ModFrame(self.vm, fqn, symtable, mod)
        w_mod = modframe.run()
        self.vm.modules_w[modname] = w_mod

    def pp(self) -> None:
        from spy.vm.module import W_Module
        color = ColorFormatter(use_colors=True)
        n = max(len(modname) for modname in self.mods)
        import_list = self.get_import_list()
        for modname in import_list:
            mod = self.mods[modname]
            if isinstance(mod, ast.Module):
                what = color.set('green', mod.filename)
            elif isinstance(mod, W_Module):
                what = color.set('blue', str(mod)) + ' (already imported)'
            elif mod is None:
                c = 'red'
                what = color.set('red', 'ImportError')
            else:
                assert False
            print(f'{modname:>{n}s} => {what}')


    # ===========================================================
    # visitor pattern to recurively find all "import" statements

    def visit(self, mod: ast.Module) -> None:
        mod.visit('visit', self)

    def visit_Import(self, imp: ast.Import) -> None:
        self.queue.append(imp.fqn.modname)

    # ===========================================================
