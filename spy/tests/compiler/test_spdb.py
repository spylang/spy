# -*- encoding: utf-8 -*-

from io import StringIO

from spy.errors import SPyError
from spy.tests.support import CompilerTest, only_interp
from spy.vm.debugger.spdb import make_spdb
from spy.vm.registry import ModuleRegistry
from spy.vm.str import W_Str

SPDB_TEST = ModuleRegistry("_spdb_test")


@SPDB_TEST.builtin_func
def w_run(vm: "SPyVM", w_commands: W_Str) -> None:
    commands = vm.unwrap_str(w_commands)
    stdin = StringIO(commands)
    stdout = StringIO()
    spdb = make_spdb(vm, stdin=stdin, stdout=stdout)
    spdb.prompt = "(spdb)\n"
    spdb.interaction()
    breakpoint()


@only_interp
class TestSPdb(CompilerTest):
    def test_simple(self):
        self.vm.make_module(SPDB_TEST)

        src = """
        import _spdb_test

        def foo(s: str) -> None:
            x = 1
            _spdb_test.run(s)
        """
        mod = self.compile(src)
        xxx = "where\ncontinue\n"
        mod.foo(xxx)
