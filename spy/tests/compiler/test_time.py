#-*- encoding: utf-8 -*-

import time
from spy.tests.support import CompilerTest

class TestTime(CompilerTest):

    def test_time(self):
        mod = self.compile(
        """
        from time import time

        def foo() -> f64:
            return time()
        """)
        a = time.time()
        result = mod.foo()
        b = time.time()
        assert a <= result <= b

    def test_sleep(self):
        mod = self.compile(
        """
        from time import time, sleep

        def foo() -> f64:
            start: f64 = time()
            sleep(0.01)
            end: f64 = time()
            return end - start
        """)
        elapsed = mod.foo()
        # Should have slept for at least 0.05 seconds
        assert elapsed >= 0.01
