import time

from spy.tests.support import CompilerTest


class TestTime(CompilerTest):
    def test_time(self):
        mod = self.compile("""
        from time import time

        def foo() -> f64:
            return time()
        """)
        a = time.time()
        result = mod.foo()
        b = time.time()
        assert a <= result <= b

    def test_sleep(self):
        mod = self.compile("""
        from time import time, sleep

        def foo() -> f64:
            start: f64 = time()
            sleep(0.01)
            end: f64 = time()
            return end - start
        """)
        elapsed = mod.foo()
        # Should have slept for at least 0.01 seconds
        if sys.platform == "emscripten":
            # Someone seems to truncate this to an f32 and then extend it back
            # to an f64. It doesn't seem to be in our WebAssembly module, so I
            # think it might be a Node problem. Anyways after this round trip it
            # can come back as 0.0099999997.
            assert elapsed >= 0.009
        else:
            assert elapsed >= 0.01
