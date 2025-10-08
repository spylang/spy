# -*- encoding: utf-8 -*-

import re

import pytest

from spy.tests.support import CompilerTest, only_C


@pytest.mark.skip(reason="this is broken, see TextBuilder.lineno docstring")
@only_C
class TestDebug(CompilerTest):
    RE_SPY_LINE = re.compile(r"#line SPY_LINE\((\d+), (\d+)\)")

    def test_debug_info(self):
        self.compile("""
        def foo() -> i32:   # line 2  <==
            x: i32 = 3      # line 3  <==
            y: i32 = 4      # line 4
            z: i32 = (5 +   # line 5
                      6)    # line 6
            return 7        # line 7  <==
        """)

        # ideally we would like to check the actual debuginfo (i.e. what
        # happens if you execute step by step in the debugger), but we don't
        # know how to do. Instead, we just check some basic properties of the
        # C code:
        #   1. that SPY_LINE(spy, c) contains the correct C line number
        #   2. that we emit only the SPY_LINE which are marked by the arrows
        csrc = self.builddir.join("test.c").read()
        spylines = []
        for lineno, line in enumerate(csrc.splitlines(), start=1):
            m = self.RE_SPY_LINE.search(line)
            if m:
                spyline = int(m.group(1))
                cline = int(m.group(2))
                assert cline == lineno + 1
                spylines.append(spyline)
        assert spylines == [2, 3, 7]
