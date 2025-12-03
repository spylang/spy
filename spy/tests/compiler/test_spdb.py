import re
import sys
import textwrap
from io import StringIO

import pytest

from spy.errors import SPyError
from spy.tests.support import CompilerTest, only_interp
from spy.util import print_diff
from spy.vm.debugger.spdb import SPdb
from spy.vm.exc import W_Traceback
from spy.vm.registry import ModuleRegistry
from spy.vm.str import W_Str
from spy.vm.vm import SPyVM

TESTMOD = ModuleRegistry("_test")


@TESTMOD.builtin_func
def w_spdb_interact(vm: "SPyVM", w_session: W_Str) -> None:
    """
    Interact with (spdb), following the given session and checking the output.
    """
    # get the W_Traceback corresponding to the current app-level frame
    pyframe = sys._getframe().f_back.f_back  # type: ignore
    assert pyframe is not None
    w_tb = W_Traceback.from_py_frame(pyframe)
    #
    session = vm.unwrap_str(w_session)
    spdb_expect(vm, w_tb, session, post_mortem=False)


def spdb_expect(vm: "SPyVM", w_tb, session: str, *, post_mortem: bool) -> None:
    """
    Simulate the given session in SPdb and check that the actual result matches.
    """
    # if we call pytest --spdb, call "breakpoint" here, but change the prompt so the get
    # the same "(spdb) " that we get in tests, so we can easily copy&paste sessions
    if vm.spdb:  # type: ignore
        spdb = SPdb(vm, w_tb)
        spdb.prompt = "(spdb) "
        if post_mortem:
            spdb.post_mortem()
        else:
            spdb.interaction()
        return

    # unwrap & dedent
    session = textwrap.dedent(session).strip()

    # find all the "(spdb) COMMAND" lines and extract all the commands; commands will be
    # something like ['where', 'up', 'll', ...]
    pattern = re.compile(r"^\(spdb\)\s*(\S.*)$", re.MULTILINE)
    commands = pattern.findall(session)

    # start a spdb session, type the given commands and get the result
    faketerm = FakeTerminal(commands)
    spdb = SPdb(vm, w_tb, stdin=faketerm, stdout=faketerm, use_colors=False)
    spdb.prompt = "(spdb) "

    if post_mortem:
        spdb.post_mortem()
    else:
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
        from _test import spdb_interact

        def foo(session: str) -> int:
            spdb_interact(session)
            return 42
        """
        session = f"""
        --- entering applevel debugger ---
           [0] test::foo at {self.filename}:5
            |     spdb_interact(session)
            |     |____________________|
        (spdb) continue
        """
        mod = self.compile(src)
        res = mod.foo(session)
        assert res == 42

    def test_where_up_down(self):
        src = """
        from _test import spdb_interact

        def foo(session: str) -> None:
            bar(session)

        def bar(session: str) -> None:
            baz(session)

        def baz(session: str) -> None:
            spdb_interact(session)
        """
        session = f"""
        --- entering applevel debugger ---
           [2] test::baz at {self.filename}:11
            |     spdb_interact(session)
            |     |____________________|
        (spdb) where
           [0] test::foo at {self.filename}:5
            |     bar(session)
            |     |__________|
           [1] test::bar at {self.filename}:8
            |     baz(session)
            |     |__________|
        *  [2] test::baz at {self.filename}:11
            |     spdb_interact(session)
            |     |____________________|
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
            |     spdb_interact(session)
            |     |____________________|
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
            |     spdb_interact(session)
            |     |____________________|
        (spdb) down
        *** Newest frame
        (spdb) continue
        """
        mod = self.compile(src)
        mod.foo(session)

    def test_longlist(self):
        src = """
        from _test import spdb_interact

        def foo(session: str) -> int:
            return bar(session)

        def bar(session: str) -> int:
            spdb_interact(session)
            return 42
        """
        session = f"""
        --- entering applevel debugger ---
           [1] test::bar at {self.filename}:8
            |     spdb_interact(session)
            |     |____________________|
        (spdb) l
           7     def bar(session: str) -> int:
           8  ->     spdb_interact(session)
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
        from _test import spdb_interact

        def foo(x: int, session: str) -> int:
            y = x + 1
            spdb_interact(session)
            return y
        """
        session = f"""
        --- entering applevel debugger ---
           [0] test::foo at {self.filename}:6
            |     spdb_interact(session)
            |     |____________________|
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
        from _test import spdb_interact

        def foo(x: int, session: str) -> None:
            spdb_interact(session)
        """
        session = f"""
        --- entering applevel debugger ---
           [0] test::foo at {self.filename}:5
            |     spdb_interact(session)
            |     |____________________|
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

    def test_post_mortem(self):
        src = """
        def foo() -> None:
            x = 1
            raise ValueError("hello")
        """
        session = f"""
        --- entering applevel debugger (post-mortem) ---
           [0] test::foo at {self.filename}:4
            |     raise ValueError("hello")
            |     |_______________________|
        (spdb) longlist
           2     def foo() -> None:
           3         x = 1
           4  ->     raise ValueError("hello")
        (spdb) x
        static type:  <spy type 'i32'>
        dynamic type: <spy type 'i32'>
        1
        (spdb) continue
        """
        mod = self.compile(src)
        try:
            mod.foo()
        except SPyError as e:
            e.add_traceback()
            w_tb = e.w_exc.w_tb
            spdb_expect(self.vm, w_tb, session, post_mortem=True)

    def test_post_mortem_doppler_longlist(self):
        self.backend = "doppler"
        src = """
        @blue
        def inc(i: int) -> int:
            return i + 1

        def foo() -> None:
            x = inc("hello")
        """
        session = f"""
        --- entering applevel debugger (post-mortem) ---
           [0] [redshift] test::foo at {self.filename}:7
            |     x = inc("hello")
            |         |__________|
        (spdb) longlist
           6     def foo() -> None:
           7  ->     x = inc("hello")
        (spdb) continue
        """
        try:
            mod = self.compile(src)
        except SPyError as e:
            e.add_traceback()
            w_tb = e.w_exc.w_tb
            spdb_expect(self.vm, w_tb, session, post_mortem=True)
