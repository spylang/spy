from spy.tests.support import CompilerTest, only_emscripten


@only_emscripten
class TestJsFFI(CompilerTest):
    def test_emscripten_run(self):
        exe = self.compile("""
        def main() -> None:
            print('hello from print')
        """)
        out = exe.run()
        assert out == "hello from print\n"

    def test_console_log(self):
        exe = self.compile("""
        from jsffi import init as js_init, get_Console

        def main() -> None:
            js_init()
            console = get_Console()
            console.log('hello from console.log')
            console.log(42)
        """)
        out = exe.run()
        assert out == "hello from console.log\n42\n"

    def test_setattr(self):
        exe = self.compile("""
        from jsffi import init as js_init, get_Console, get_GlobalThis

        def main() -> None:
            js_init()
            globalThis = get_GlobalThis()
            console = get_Console()
            globalThis.xxx = "hello 1"
            console.log(globalThis.xxx)
            globalThis.xxx = "hello 2"
            console.log(globalThis.xxx)
        """)
        out = exe.run()
        assert out == "hello 1\nhello 2\n"

    def test_callback(self):
        exe = self.compile("""
        from jsffi import init as js_init, get_GlobalThis

        def say_hello() -> None:
            print("hello from callback")

        def main() -> None:
            js_init()
            globalThis = get_GlobalThis()
            globalThis.setTimeout(say_hello) # XXX allow 2 params and pass 0
        """)
        out = exe.run()
        assert out == "hello from callback\n"

    def test_call_method_2(self):
        exe = self.compile("""
        from jsffi import init as js_init, get_GlobalThis

        def main() -> None:
            js_init()
            globalThis = get_GlobalThis()
            result = globalThis.Math.max(3, 7)
            globalThis.console.log(result)
        """)
        out = exe.run()
        assert out == "7\n"

    def test_call_method_3(self):
        exe = self.compile("""
        from jsffi import init as js_init, get_GlobalThis

        def main() -> None:
            js_init()
            globalThis = get_GlobalThis()
            result = globalThis.Math.min(3, 7, 1)
            globalThis.console.log(result)
        """)
        out = exe.run()
        assert out == "1\n"

    def test_to_i32(self):
        exe = self.compile("""
        from jsffi import init as js_init, get_GlobalThis, js_to_i32

        def main() -> None:
            js_init()
            globalThis = get_GlobalThis()
            globalThis.testVal = 42
            ref = globalThis.testVal
            x: i32 = js_to_i32(ref)
            print(x)
        """)
        out = exe.run()
        assert out == "42\n"

    def test_to_f64(self):
        exe = self.compile("""
        from jsffi import init as js_init, get_GlobalThis, js_to_f64

        def main() -> None:
            js_init()
            globalThis = get_GlobalThis()
            globalThis.testVal = 3.14
            ref = globalThis.testVal
            x: f64 = js_to_f64(ref)
            print(x)
        """)
        out = exe.run()
        assert out == "3.140000\n"

    def test_u8array_from_ptr(self):
        # Check that jsffi_u8array_from_ptr returns a JsRef without crashing
        # and that the Uint8ClampedArray has the expected length.
        exe = self.compile("""
        from jsffi import init as js_init, get_GlobalThis, js_u8array_from_ptr
        from unsafe import gc_alloc

        def main() -> None:
            js_init()
            globalThis = get_GlobalThis()
            buf = gc_alloc[u8](12)
            arr = js_u8array_from_ptr(buf, 12)
            globalThis.console.log(arr.length)
        """)
        out = exe.run()
        assert out == "12\n"
