import os
import pickle
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Union

import py.path

from spy import ast
from spy.analyze.scope import ScopeAnalyzer
from spy.fqn import FQN
from spy.parser import Parser
from spy.textbuilder import ColorFormatter
from spy.util import OrderedSet
from spy.vm.modframe import ModFrame

if TYPE_CHECKING:
    from spy.vm.module import W_Module
    from spy.vm.vm import SPyVM

MODULE = Union[ast.Module, "W_Module", None]

# Cache version: increment this when ast.Module or SymTable structure changes
SPYC_VERSION = 2


@dataclass
class CacheError:
    """Records an error that occurred during cache operations."""

    spyc: str
    operation: str  # "load" or "save"
    error_message: str


class ImportAnalyzer:
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

        main
        ├── aaa
        │   ├── a1
        │   └── a2
        └── bbb
            ├── aaa (already seen)
            ├── b1
            └── b2

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

    def __init__(self, vm: "SPyVM", modname: str, use_spyc: bool = True) -> None:
        self.vm = vm
        self.queue = deque([modname])
        self.mods: dict[str, MODULE] = {}
        self.deps: dict[str, OrderedSet[str]] = {}  # modname -> list_of_imports
        self.cur_modname: Optional[str] = None
        self.cached_mods: dict[str, py.path.local] = {}  # modname -> cache file path
        self.cache_errors: list[CacheError] = []  # List of all cache errors
        self.use_spyc = use_spyc

    def getmod(self, modname: str) -> ast.Module:
        mod = self.mods[modname]
        assert isinstance(mod, ast.Module)
        return mod

    def _get_spyc(self, spyfile: py.path.local) -> py.path.local:
        """
        Get the path to the cache file for a given .spy file.
        """
        pycache = spyfile.dirpath("__pycache__")
        spyc = pycache.join(f"{spyfile.purebasename}.spyc")
        return spyc

    def _is_spyc_valid(self, spyfile: py.path.local, spyc: py.path.local) -> bool:
        """
        Check if the cache file is valid (newer than the source file).
        """
        if not spyc.check():
            return False
        return spyc.mtime() > spyfile.mtime()

    def _load_spyc(
        self, spyfile: py.path.local, spyc: py.path.local, modname: str
    ) -> Optional[ast.Module]:
        """
        Load a module from .spyc file.
        """
        try:
            with spyc.open("rb") as f:
                data = pickle.load(f)
            if data["version"] == SPYC_VERSION:
                # cache is valid
                mod = data["module"]
                assert isinstance(mod, ast.Module)
                assert mod.filename == str(spyfile)
                self.cached_mods[modname] = spyc
                return mod
            else:
                # Version mismatch - record error and invalidate cache
                cache_version = data["version"]
                error = CacheError(
                    spyc=str(spyc),
                    operation="load",
                    error_message=f"Version mismatch: cache has version {cache_version}, expected {SPYC_VERSION}",
                )
                self.cache_errors.append(error)
                return None
        except Exception as e:
            # Record the error
            error = CacheError(
                spyc=str(spyc),
                operation="load",
                error_message=str(e),
            )
            self.cache_errors.append(error)

            # cli.py has robust_import_caching enabled: in that case we just want to
            # ignore this error. But during tests, we want to always raise it.
            if not self.vm.robust_import_caching:
                raise

            # Otherwise, return None to force re-parsing
            return None

    def _save_spyc(self, mod: ast.Module, spyc: py.path.local) -> None:
        """
        Save a module to cache file with version information.
        """
        try:
            spyc.dirpath().ensure(dir=True)
            data = {"version": SPYC_VERSION, "module": mod}
            with spyc.open("wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            # Record the error
            error = CacheError(
                spyc=str(spyc),
                operation="save",
                error_message=str(e),
            )
            self.cache_errors.append(error)

            # cli.py has robust_import_caching enabled: in that case we just want to
            # ignore this error. But during tests, we want to always raise it.
            if not self.vm.robust_import_caching:
                raise

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

            elif spyfile := self.vm.find_file_on_path(modname):
                # Initialize the dependency list for this module
                if modname not in self.deps:
                    self.deps[modname] = OrderedSet()

                mod = self.parse_one(modname, spyfile)
                self.mods[modname] = mod

                # record implicit imports
                assert mod.symtable is not None
                for imp_modname in mod.symtable.implicit_imports:
                    self.record_import(modname, imp_modname)

                # record explicit imports
                self.cur_modname = modname
                self.visit(mod)
                self.cur_modname = None

            else:
                # we couldn't find .spy for this modname
                self.mods[modname] = None

    def parse_one(self, modname: str, spyfile: py.path.local) -> ast.Module:
        """
        Parse a module AND run ScopeAnalyzer on it.
        """
        # try to load from cache first
        mod = None
        if self.use_spyc:
            spyc = self._get_spyc(spyfile)
            if self._is_spyc_valid(spyfile, spyc):
                mod = self._load_spyc(spyfile, spyc, modname)
                if mod is not None:
                    return mod

        # no cache found, parse it
        parser = Parser.from_filename(str(spyfile))
        mod = parser.parse()
        scopes = self.analyze_one(modname, mod)
        mod.symtable = scopes.by_module()

        if self.use_spyc:
            self._save_spyc(mod, spyc)
        return mod

    def analyze_one(self, modname: str, mod: ast.Module) -> ScopeAnalyzer:
        scopes = ScopeAnalyzer(self.vm, modname, mod)
        scopes.analyze()
        return scopes

    def get_import_list(self) -> list[str]:
        """
        Return a list of module names in the order they should be imported.

        This implements a depth-first post-order traversal of the import tree,
        which corresponds to the order described in the class docstring.
        """
        # Perform depth-first post-order traversal using the dependency graph
        result = []
        visited = set()

        def visit(modname: str) -> None:
            if modname in visited:
                return
            visited.add(modname)

            # Visit all dependencies first
            for dep in self.deps.get(modname, OrderedSet()):
                visit(dep)

            # Then add this module
            result.append(modname)

        # Start with all modules to ensure we cover everything
        for modname in self.mods:
            visit(modname)

        return result

    def import_all(self) -> None:
        assert self.mods, "call .parse_all() first"
        import_list = self.get_import_list()
        for modname in import_list:
            mod = self.mods[modname]
            if isinstance(mod, ast.Module):
                self.import_one(modname, mod)

    def import_one(self, modname: str, mod: ast.Module) -> None:
        assert mod.symtable is not None
        fqn = FQN(modname)
        modframe = ModFrame(self.vm, fqn, mod)
        w_mod = modframe.run()
        self.vm.modules_w[modname] = w_mod

    def pp(self) -> None:
        print("Import tree:")
        self.pp_tree()
        print()
        print("vm.path:")
        self.pp_path()
        print()
        print("Import order:")
        self.pp_list()
        print()
        self.pp_cache_errors()

    def pp_cache_errors(self) -> None:
        """Print cache errors if any occurred."""
        if not self.cache_errors:
            return

        color = ColorFormatter(use_colors=True)
        print(color.set("red", "Cache errors:"))
        for err in self.cache_errors:
            print(f"  {err.operation} {color.set('yellow', err.spyc)}:")
            print(f"    {err.error_message}")

    def pp_path(self) -> None:
        color = ColorFormatter(use_colors=True)
        for i, p in enumerate(self.vm.path):
            print(f"  p{i} = {p}")

    def pp_list(self) -> None:
        from spy.vm.module import W_Module

        color = ColorFormatter(use_colors=True)
        n = max(len(modname) for modname in self.mods)
        import_list = self.get_import_list()

        # identify common paths
        paths = {}
        if self.vm.path:
            for i, path in enumerate(self.vm.path):
                paths[path + "/"] = f"$p{i}"

        def shorten_path(path: str) -> str:
            if not path:
                return path
            for base_path, alias in paths.items():
                if path.startswith(base_path):
                    suffix = path[len(base_path) :]
                    suffix = color.set("green", suffix)
                    return f"{alias}/{suffix}"
            return path

        # Print import list with shortened paths
        for i, modname in enumerate(import_list):
            mod = self.mods[modname]
            if isinstance(mod, ast.Module):
                # The alias is already colored in shorten_path
                what = shorten_path(mod.filename)
                if modname in self.cached_mods:
                    what += " (cached)"

            elif isinstance(mod, W_Module):
                what = color.set("blue", str(mod)) + " (already imported)"
            elif mod is None:
                what = color.set("red", "ImportError")
            else:
                assert False
            print(f"{i:>3d} {modname:>{n}s} => {what}")

    def pp_tree(self) -> None:
        """
        Print the import tree using tree-like format similar to the 'tree' command.

        Example:
        main
        ├── aaa
        │   ├── a1
        │   └── a2
        └── bbb
            ├── aaa (already seen)
            ├── b1
            └── b2
        """
        assert self.mods, "call .parse_all() first"

        # Constants for tree formatting
        # fmt: off
        CROSS  = "├── "
        BAR    = "│   "
        CORNER = "└── "
        SPACE  = "    "
        # fmt: on

        # Find the root module(s) - those that are not imported by any other module
        all_imports: set[str] = set()
        for imports in self.deps.values():
            all_imports.update(imports)

        roots = [mod for mod in self.mods if mod not in all_imports]

        # We expect at least one root (the entry point)
        if not roots:
            roots = [next(iter(self.mods))]

        # Define recursive printer function
        def print_tree(
            modname: str, prefix: str, indent: str, marker: str, visited: set
        ) -> None:
            if modname in visited:
                print(f"{prefix}{marker}{modname} (already seen)")
                return

            print(f"{prefix}{marker}{modname}")
            visited.add(modname)

            # Get the dependencies of this module
            deps = list(self.deps.get(modname, OrderedSet()))
            if not deps:
                return

            new_prefix = prefix + indent

            # Process all child modules
            for dep in deps[:-1]:  # All but the last
                print_tree(dep, new_prefix, BAR, CROSS, visited)

            # Last child gets a corner marker
            print_tree(deps[-1], new_prefix, SPACE, CORNER, visited)

        # Print each root
        for root in roots:
            print_tree(root, prefix="  ", indent="", marker="", visited=set())

    # ===========================================================
    # visitor pattern to recurively find all "import" statements

    def visit(self, mod: ast.Module) -> None:
        mod.visit("visit", self)

    def visit_Import(self, imp: ast.Import) -> None:
        assert self.cur_modname is not None
        self.record_import(self.cur_modname, imp.ref.modname)

    def record_import(self, cur_modname: str, modname: str) -> None:
        if modname == "builtins":
            return
        self.deps[cur_modname].add(modname)
        self.queue.append(modname)

    # ===========================================================
