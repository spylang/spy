import textwrap

import py.path
import pytest

from spy import ast
from spy.analyze.importing import ImportAnalyzer
from spy.vm.vm import SPyVM


@pytest.mark.usefixtures("init")
class TestImportAnalyzer:
    @pytest.fixture
    def init(self, tmpdir):
        self.vm = SPyVM()
        self.vm.path = [str(tmpdir)]
        self.tmpdir = tmpdir

    def write(self, filename: str, src: str) -> py.path.local:
        src = textwrap.dedent(src)
        f = self.tmpdir.join(filename)
        f.dirpath().ensure(dir=True)  # create directories, if needed
        f.write(src)
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
        scopes = analyzer.analyze_scopes("main")
        assert scopes.by_module().name == "main"

    def test_vm_path(self):
        # we write mod1 in an unrelated dir, which is the added to vm.path
        self.write("mylib/mod1.spy", "x: i32 = 42")
        self.write("main.spy", "import mod1")
        self.vm.path.append(self.tmpdir.join("mylib"))
        analyzer = ImportAnalyzer(self.vm, "main")
        analyzer.parse_all()
        assert list(analyzer.mods) == ["main", "mod1"]
        assert analyzer.mods["mod1"] is not None  # check that we found it
