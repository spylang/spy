from typing import Any, Optional
import textwrap
import pytest
import py.path
from spy import ast
from spy.fqn import FQN
from spy.parser import Parser
from spy.analyze.importing import ImportAnalizyer
from spy.vm.vm import SPyVM
from spy.vm.module import W_Module
from spy.tests.support import expect_errors


@pytest.mark.usefixtures('init')
class TestImportAnalizyer:

    @pytest.fixture
    def init(self, tmpdir):
        self.vm = SPyVM()
        self.vm.path = [str(tmpdir)]
        self.tmpdir = tmpdir

    def write(self, filename: str, src: str) -> py.path.local:
        src = textwrap.dedent(src)
        f = self.tmpdir.join(filename)
        f.write(src)
        return f

    def test_simple_import(self):
        self.write("mod1.spy", """
        x: i32 = 42
        """)
        self.write("main.spy", """
        import mod1
        """)
        analyzer = ImportAnalizyer(self.vm, 'main')
        analyzer.parse_all()

        assert list(analyzer.mods) == ['main', 'mod1']
        assert isinstance(analyzer.mods['main'], ast.Module)
        assert isinstance(analyzer.mods['mod1'], ast.Module)

    def test_nested_imports(self):
        self.write("main.spy", """
        import mod1
        import mod2
        """)
        self.write("mod1.spy", """
        import mod3
        """)
        self.write("mod2.spy", """
        import mod3
        import mod4
        """)
        self.write("mod3.spy", """
        x: i32 = 42
        """)
        self.write("mod4.spy", """
        y: i32 = 43
        """)

        analyzer = ImportAnalizyer(self.vm, 'main')
        analyzer.parse_all()
        assert list(analyzer.mods) == ['main', 'mod1', 'mod2', 'mod3', 'mod4']

    @pytest.mark.skip(reason="parser does not support this")
    def test_import_in_function(self):
        self.write("main.spy", """
        def foo() -> void:
            import mod1
        """)
        self.write("mod1.spy", """
        x: i32 = 42
        """)
        analyzer = ImportAnalizyer(self.vm, 'main')
        analyzer.parse_all()
        assert list(analyzer.mods) == ['main', 'mod1']

    def test_missing_module(self):
        self.write("main.spy", """
        import nonexistent
        """)

        analyzer = ImportAnalizyer(self.vm, 'main')
        analyzer.parse_all()
        assert list(analyzer.mods) == ['main', 'nonexistent']
        assert isinstance(analyzer.mods['main'], ast.Module)
        assert analyzer.mods['nonexistent'] is None

    def test_already_imported_module(self):
        self.write("main.spy", """
        import mod1
        """)
        self.write("mod1.spy", """
        x: i32 = 42
        """)

        # Pre-import mod1 into the VM
        dummy_module = object()
        self.vm.modules_w['mod1'] = dummy_module

        analyzer = ImportAnalizyer(self.vm, 'main')
        analyzer.parse_all()
        assert list(analyzer.mods) == ['main', 'mod1']
        assert analyzer.mods['mod1'] is dummy_module

    def test_analyze_scopes(self):
        self.write("main.spy", """
        x: i32 = 42
        """)
        analyzer = ImportAnalizyer(self.vm, 'main')
        analyzer.parse_all()
        scopes = analyzer.analyze_scopes('main')
        assert scopes.by_module().name == 'main'

    def test_get_filename(self):
        self.write("main.spy", """
        x: i32 = 42
        """)
        analyzer = ImportAnalizyer(self.vm, 'main')
        filename = analyzer.get_filename('main')
        assert filename == self.tmpdir.join('main.spy')
        assert analyzer.get_filename('nonexistent') is None
