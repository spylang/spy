import textwrap

import py.path
import pytest

from spy import ast
from spy.analyze import importing
from spy.analyze.importing import SPYC_VERSION, ImportAnalyzer
from spy.vm.vm import SPyVM


@pytest.mark.usefixtures("init")
class TestImportAnalyzer:
    @pytest.fixture
    def init(self, tmpdir):
        self.vm = SPyVM()
        self.vm.path = [str(tmpdir)]
        self.tmpdir = tmpdir

    def write(self, filename: str, src: str, mtime_delta: float = 0) -> py.path.local:
        src = textwrap.dedent(src)
        f = self.tmpdir.join(filename)
        f.dirpath().ensure(dir=True)  # create directories, if needed
        f.write(src)
        if mtime_delta != 0:
            f.setmtime(f.mtime() + mtime_delta)
        return f

    def test_simple_import(self):
        src = """
        x: i32 = 42
        """
        self.write("mod1.spy", src)
        src = """
        import mod1
        """
        self.write("main.spy", src)
        analyzer = ImportAnalyzer(self.vm, "main")
        analyzer.parse_all()

        assert list(analyzer.mods) == ["main", "mod1"]
        assert isinstance(analyzer.mods["main"], ast.Module)
        assert isinstance(analyzer.mods["mod1"], ast.Module)

    def test_nested_imports(self):
        src = """
        import aaa
        import bbb
        """
        self.write("main.spy", src)
        src = """
        import a1
        import a2
        """
        self.write("aaa.spy", src)
        src = """
        import aaa
        import b1
        import b2
        """
        self.write("bbb.spy", src)
        src = """
        x = 'a1'
        """
        self.write("a1.spy", src)
        src = """
        x = 'a2'
        """
        self.write("a2.spy", src)
        src = """
        x = 'b1'
        """
        self.write("b1.spy", src)
        src = """
        x = 'b2'
        """
        self.write("b2.spy", src)

        analyzer = ImportAnalyzer(self.vm, "main")
        analyzer.parse_all()
        mods = analyzer.get_import_list()
        assert mods == ["a1", "a2", "aaa", "b1", "b2", "bbb", "main"]

    @pytest.mark.skip(reason="parser does not support this")
    def test_import_in_function(self):
        src = """
        def foo() -> None:
            import mod1
        """
        self.write("main.spy", src)
        src = """
        x: i32 = 42
        """
        self.write("mod1.spy", src)
        analyzer = ImportAnalyzer(self.vm, "main")
        analyzer.parse_all()
        assert list(analyzer.mods) == ["main", "mod1"]

    def test_missing_module(self):
        src = "import nonexistent"
        self.write("main.spy", src)

        analyzer = ImportAnalyzer(self.vm, "main")
        analyzer.parse_all()
        assert list(analyzer.mods) == ["main", "nonexistent"]
        assert isinstance(analyzer.mods["main"], ast.Module)
        assert analyzer.mods["nonexistent"] is None

    def test_already_imported_module(self):
        self.write("main.spy", "import mod1")
        self.write("mod1.spy", "x: i32 = 42")

        # Pre-import mod1 into the VM
        dummy_module = object()
        self.vm.modules_w["mod1"] = dummy_module  # type: ignore

        analyzer = ImportAnalyzer(self.vm, "main")
        analyzer.parse_all()
        assert list(analyzer.mods) == ["main", "mod1"]
        assert analyzer.mods["mod1"] is dummy_module

    def test_analyze_scopes(self):
        self.write("main.spy", "x: i32 = 42")
        analyzer = ImportAnalyzer(self.vm, "main")
        analyzer.parse_all()
        mod = analyzer.mods["main"]
        assert isinstance(mod, ast.Module)
        assert mod.symtable is not None
        assert mod.symtable.name == "main"

    def test_vm_path(self):
        # we write mod1 in an unrelated dir, which is the added to vm.path
        self.write("mylib/mod1.spy", "x: i32 = 42")
        self.write("main.spy", "import mod1")
        self.vm.path.append(self.tmpdir.join("mylib"))
        analyzer = ImportAnalyzer(self.vm, "main")
        analyzer.parse_all()
        assert list(analyzer.mods) == ["main", "mod1"]
        assert analyzer.mods["mod1"] is not None  # check that we found it

    def test_cache_basic(self):
        src = "x: i32 = 42"
        self.write("mod1.spy", src, mtime_delta=-1)

        # First import - create .spyc
        analyzer1 = ImportAnalyzer(self.vm, "mod1")
        analyzer1.parse_all()
        analyzer1.import_all()
        assert self.tmpdir.join("__pycache__", "mod1.spyc").exists()

        # Second import with fresh VM - should use .spyc
        vm2 = SPyVM()
        vm2.path = [str(self.tmpdir)]
        analyzer2 = ImportAnalyzer(vm2, "mod1")
        analyzer2.parse_all()
        assert "mod1" in analyzer2.cached_mods

    def test_cache_invalidation(self):
        src1 = "x: i32 = 42"
        f = self.write("mod1.spy", src1, mtime_delta=-1)

        # First import - create .spyc
        analyzer1 = ImportAnalyzer(self.vm, "mod1")
        analyzer1.parse_all()
        analyzer1.import_all()
        spyc_file = self.tmpdir.join("__pycache__", "mod1.spyc")
        assert spyc_file.exists()
        spyc_mtime = spyc_file.mtime()

        # Modify the source file and set its mtime to be newer than cache
        src2 = "y: i32 = 100"
        f.write(src2)
        f.setmtime(spyc_mtime + 1)

        # Second import with fresh VM - should re-parse (cache is older than source)
        vm2 = SPyVM()
        vm2.path = [str(self.tmpdir)]
        analyzer2 = ImportAnalyzer(vm2, "mod1")
        analyzer2.parse_all()
        assert "mod1" not in analyzer2.cached_mods

        # Import to update cache
        analyzer2.import_all()

        # Cache should be updated
        assert spyc_file.mtime() > spyc_mtime

    def test_cache_with_imports(self):
        self.write("a.spy", "x: i32 = 1", mtime_delta=-1)
        self.write("b.spy", "import a\ny: i32 = 2", mtime_delta=-1)
        self.write("main.spy", "import b", mtime_delta=-1)

        # First run - create caches
        analyzer1 = ImportAnalyzer(self.vm, "main")
        analyzer1.parse_all()
        analyzer1.import_all()

        # Check all cache files exist
        assert self.tmpdir.join("__pycache__", "a.spyc").exists()
        assert self.tmpdir.join("__pycache__", "b.spyc").exists()
        assert self.tmpdir.join("__pycache__", "main.spyc").exists()

        # Second run with fresh VM - should use all caches
        vm2 = SPyVM()
        vm2.path = [str(self.tmpdir)]
        analyzer2 = ImportAnalyzer(vm2, "main")
        analyzer2.parse_all()
        assert "a" in analyzer2.cached_mods
        assert "b" in analyzer2.cached_mods
        assert "main" in analyzer2.cached_mods

    def test_cache_preserves_symtable(self):
        src = "x: i32 = 42"
        self.write("mod1.spy", src, mtime_delta=-1)

        # First import with analysis
        analyzer1 = ImportAnalyzer(self.vm, "mod1")
        analyzer1.parse_all()
        analyzer1.import_all()  # This sets symtable and saves cache
        symtable1 = analyzer1.getmod("mod1").symtable

        assert symtable1 is not None

        # Second import with fresh VM should load from cache with symtable
        vm2 = SPyVM()
        vm2.path = [str(self.tmpdir)]
        analyzer2 = ImportAnalyzer(vm2, "mod1")
        analyzer2.parse_all()
        assert "mod1" in analyzer2.cached_mods

        # The cached module should already have symtable
        mod2 = analyzer2.getmod("mod1")
        assert mod2.symtable is not None
        assert mod2.symtable.name == "mod1"

    def test_cache_version_mismatch(self, monkeypatch):
        src = "x: i32 = 42"
        self.write("mod1.spy", src, mtime_delta=-1)

        # First import - create cache with current version
        analyzer1 = ImportAnalyzer(self.vm, "mod1")
        analyzer1.parse_all()
        analyzer1.import_all()
        assert self.tmpdir.join("__pycache__", "mod1.spyc").exists()

        # Second import with different SPYC_VERSION should not use cache
        monkeypatch.setattr(importing, "SPYC_VERSION", SPYC_VERSION + 1)
        vm2 = SPyVM()
        vm2.path = [str(self.tmpdir)]
        analyzer2 = ImportAnalyzer(vm2, "mod1")
        analyzer2.parse_all()
        assert "mod1" not in analyzer2.cached_mods

        # A version mismatch error should be recorded
        assert len(analyzer2.cache_errors) == 1
        error = analyzer2.cache_errors[0]
        assert error.operation == "load"
        assert "Version mismatch" in error.error_message
        assert f"version {SPYC_VERSION}" in error.error_message
        assert f"expected {SPYC_VERSION + 1}" in error.error_message

    def test_use_spyc_disabled(self):
        src = "x: i32 = 42"
        self.write("mod1.spy", src, mtime_delta=-1)

        # Import with use_spyc=False should not create .spyc
        analyzer1 = ImportAnalyzer(self.vm, "mod1", use_spyc=False)
        analyzer1.parse_all()
        analyzer1.import_all()
        assert not self.tmpdir.join("__pycache__", "mod1.spyc").exists()

        # Create cache file with a different VM and analyzer
        vm2 = SPyVM()
        vm2.path = [str(self.tmpdir)]
        analyzer2 = ImportAnalyzer(vm2, "mod1", use_spyc=True)
        analyzer2.parse_all()
        analyzer2.import_all()
        assert self.tmpdir.join("__pycache__", "mod1.spyc").exists()

        # Import with use_spyc=False should not use existing cache
        vm3 = SPyVM()
        vm3.path = [str(self.tmpdir)]
        analyzer3 = ImportAnalyzer(vm3, "mod1", use_spyc=False)
        analyzer3.parse_all()
        assert "mod1" not in analyzer3.cached_mods

    def test_duplicate_imports_deduplicated(self):
        src = """
        x: i32 = 1
        y: i32 = 2
        z: i32 = 3
        """
        self.write("aaa.spy", src)
        src = """
        from aaa import x
        from aaa import y
        import aaa
        from aaa import z
        """
        self.write("main.spy", src)

        analyzer = ImportAnalyzer(self.vm, "main")
        analyzer.parse_all()

        # "aaa" should appear only once in the dependency list for "main"
        assert "main" in analyzer.deps
        deps_list = list(analyzer.deps["main"])
        assert deps_list.count("aaa") == 1
        assert deps_list == ["aaa"]

        # The import order should only contain each module once
        import_list = analyzer.get_import_list()
        assert import_list == ["aaa", "main"]

    def test_implicit_imports(self):
        src = """
        def foo() -> None:
            for x in range(10):
                pass
        """
        # initial import
        self.write("main.spy", src, mtime_delta=-1)
        analyzer = ImportAnalyzer(self.vm, "main")
        analyzer.parse_all()
        import_list = analyzer.get_import_list()
        assert import_list == ["_range", "main"]
        #
        # second import, load from .spyc
        vm2 = SPyVM()
        vm2.path = [str(self.tmpdir)]
        analyzer2 = ImportAnalyzer(vm2, "main")
        analyzer2.parse_all()
        assert "main" in analyzer2.cached_mods
        import_list = analyzer2.get_import_list()
        assert import_list == ["_range", "main"]
