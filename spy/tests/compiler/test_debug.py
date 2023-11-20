#-*- encoding: utf-8 -*-

import pytest
from spy.vm.codeobject import OpCode
from spy.tests.support import CompilerTest, skip_backends, no_backend

class TestDebug(CompilerTest):

    def test_debug_info(self):
        mod = self.compile(
        """
        def foo(a: i32, b: i32) -> i32:   # line 2
            return (a +                   # line 3
                    b)                    # line 4
        """)
        if self.backend == 'interp':
            w_mod = self.w_mod
            w_func = w_mod.getattr_userfunc('foo')
            w_code = w_func.w_code
            assert w_code.lineno == 2
            assert w_code.body[w_code.end_prologue:] == [
                OpCode('line', 3),
                OpCode('load_local', 'a'),
                OpCode('line', 4),
                OpCode('load_local', 'b'),
                OpCode('line', 3),
                OpCode('i32_add'),
                OpCode('return'),
                OpCode('line', 4),
                OpCode('abort', 'reached the end of the function without a `return`')
            ]
        elif self.backend == 'C':
            # XXX write a test, but how?
            pass
        else:
            assert False
