#-*- encoding: utf-8 -*-
# mypy: ignore-errors

import pytest
from spy.vm.codeobject import OpCode
from spy.tests.support import CompilerTest, skip_backends, no_backend

@pytest.mark.skip("fixme")
class TestDebug(CompilerTest):

    def test_debug_info(self, legacy):
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
            assert w_code.equals("""
            line 3
            load_local a
            line 4
            load_local b
            line 3
            i32_add
            return
            line 4
            abort 'reached the end of the function without a `return`'
            """)
        elif self.backend == 'C':
            # XXX write a test, but how?
            pass
        else:
            assert False
