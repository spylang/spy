# -*- encoding: utf-8 -*-

import re
import textwrap
from io import StringIO

import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, only_interp
from spy.util import print_diff
from spy.vm.debugger.spdb import make_spdb
from spy.vm.registry import ModuleRegistry
from spy.vm.str import W_Str
from spy.vm.vm import SPyVM

TESTMOD = ModuleRegistry("_test")


@TESTMOD.builtin_func
def w_spdb_expect(vm: "SPyVM", w_session: W_Str) -> None:
    """
    Interact with (spdb), trying to simulate the given session and check that the
    actual result matches.
    """
    # if we call pytest --spdb, call "breakpoint" here, but change the prompt so the get
    # the same "(spdb) " that we get in tests, so we can easily copy&paste sessions
    if vm.spdb:  # type: ignore
        spdb = make_spdb(vm)
        spdb.prompt = "(spdb) "
        spdb.interaction()

    # unwrap & dedent
    session = vm.unwrap_str(w_session)
    session = textwrap.dedent(session).strip()

    # find all the "(spdb) COMMAND" lines and extract all the commands; commands will be
    # something like ['where', 'up', 'll', ...]
    pattern = re.compile(r"^\(spdb\)\s*(\S.*)$", re.MULTILINE)
    commands = pattern.findall(session)

    # start a spdb session, type the given commands and get the result
    faketerm = FakeTerminal(commands)
    spdb = make_spdb(vm, stdin=faketerm, stdout=faketerm, use_colors=False)
    spdb.prompt = "(spdb) "
    spdb.interaction()
    out = faketerm.get_output().strip()

    # check that the final output matches the initial session
    if session != out:
        print_diff(session, out, "expected", "got")
        pytest.fail("spdb_expect failed")


class FakeTerminal:
    """
    Simulate a terminal for SPdb tests.
    This is just enough to work with cmd.Cmd, which SPdb inherits from.

    It maintains a list of commands to "type", which are returned one by one when cmd
    calls .readline(), and it records the output.
    """

    def __init__(self, input_lines: list[str]) -> None:
        self.input_lines = input_lines
        self.input_iter = iter(input_lines)
        self.buf = StringIO()

    def readline(self) -> str:
        line = next(self.input_iter, "")
        if line == "":
            # we reached EOF. This should never happen in tests
            raise Exception(
                "EOF when reading from FakeTerminal. Maybe you forgot '(spdb) continue'?"
            )
        # simulate the user typing 'line' to the terminal
        self.buf.write(line + "\n")
        return line

    def write(self, s: str) -> None:
        self.buf.write(s)

    def flush(self) -> None:
        pass

    def get_output(self) -> str:
        return self.buf.getvalue()


@only_interp
@pytest.mark.usefixtures("initspdb")
class TestSPdb(CompilerTest):
    SKIP_SPY_BACKEND_SANITY_CHECK = True

    @pytest.fixture
    def initspdb(self, request):
        self.vm.make_module(TESTMOD)
        self.vm.spdb = request.config.option.spdb  # type: ignore

    @property
    def filename(self) -> str:
        return str(self.tmpdir.join("test.spy"))

    def test_simple(self):
        src = """
        from _test import spdb_expect

        def foo(session: str) -> int:
            spdb_expect(session)
            return 42
        """
        session = f"""
        --- entering applevel debugger ---
           [0] test::foo at {self.filename}:5
            |     spdb_expect(session)
            |     |__________________|
        (spdb) continue
        """
        mod = self.compile(src)
        res = mod.foo(session)
        assert res == 42

    def test_where_up_down(self):
        src = """
        from _test import spdb_expect

        def foo(session: str) -> None:
            bar(session)

        def bar(session: str) -> None:
            baz(session)

        def baz(session: str) -> None:
            spdb_expect(session)
        """
        session = f"""
        --- entering applevel debugger ---
           [2] test::baz at {self.filename}:11
            |     spdb_expect(session)
            |     |__________________|
        (spdb) where
           [0] test::foo at {self.filename}:5
            |     bar(session)
            |     |__________|
           [1] test::bar at {self.filename}:8
            |     baz(session)
            |     |__________|
        *  [2] test::baz at {self.filename}:11
            |     spdb_expect(session)
            |     |__________________|
        (spdb) up
           [1] test::bar at {self.filename}:8
            |     baz(session)
            |     |__________|
        (spdb) where
           [0] test::foo at {self.filename}:5
            |     bar(session)
            |     |__________|
        *  [1] test::bar at {self.filename}:8
            |     baz(session)
            |     |__________|
           [2] test::baz at {self.filename}:11
            |     spdb_expect(session)
            |     |__________________|
        (spdb) up
           [0] test::foo at {self.filename}:5
            |     bar(session)
            |     |__________|
        (spdb) up
        *** Oldest frame
        (spdb) down
           [1] test::bar at {self.filename}:8
            |     baz(session)
            |     |__________|
        (spdb) down
           [2] test::baz at {self.filename}:11
            |     spdb_expect(session)
            |     |__________________|
        (spdb) down
        *** Newest frame
        (spdb) continue
        """
        mod = self.compile(src)
        mod.foo(session)

    def test_longlist(self):
        src = """
        from _test import spdb_expect

        def foo(session: str) -> int:
            return bar(session)

        def bar(session: str) -> int:
            spdb_expect(session)
            return 42
        """
        session = f"""
        --- entering applevel debugger ---
           [1] test::bar at {self.filename}:8
            |     spdb_expect(session)
            |     |__________________|
        (spdb) l
           7     def bar(session: str) -> int:
           8  ->     spdb_expect(session)
           9         return 42
        (spdb) up
           [0] test::foo at {self.filename}:5
            |     return bar(session)
            |            |__________|
        (spdb) l
           4     def foo(session: str) -> int:
           5  ->     return bar(session)
        (spdb) continue
        """
        mod = self.compile(src)
        res = mod.foo(session)
        assert res == 42

    def test_print(self):
        src = """
        from _test import spdb_expect

        def foo(x: int, session: str) -> int:
            y = x + 1
            spdb_expect(session)
            return y
        """
        session = f"""
        --- entering applevel debugger ---
           [0] test::foo at {self.filename}:6
            |     spdb_expect(session)
            |     |__________________|
        (spdb) print x
        static type:  <spy type 'i32'>
        dynamic type: <spy type 'i32'>
        41
        (spdb) y
        static type:  <spy type 'i32'>
        dynamic type: <spy type 'i32'>
        42
        (spdb) y * 2
        static type:  <spy type 'i32'>
        dynamic type: <spy type 'i32'>
        84
        (spdb) continue
        """
        mod = self.compile(src)
        res = mod.foo(41, session)
        assert res == 42

    def test_name_lookup(self):
        src = """
        from _test import spdb_expect

        def foo(x: int, session: str) -> None:
            spdb_expect(session)
        """
        session = f"""
        --- entering applevel debugger ---
           [0] test::foo at {self.filename}:5
            |     spdb_expect(session)
            |     |__________________|
        (spdb) x
        static type:  <spy type 'i32'>
        dynamic type: <spy type 'i32'>
        42
        (spdb) y
        *** NameError: name `y` is not defined
        (spdb) continue
        """
        mod = self.compile(src)
        mod.foo(42, session)
