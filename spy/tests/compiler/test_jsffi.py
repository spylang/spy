from spy.tests.support import CompilerTest, only_emscripten


@only_emscripten
class TestJsFFI(CompilerTest):
    def test_emscripten_run(self):
        src = """
        def main() -> None:
            print('hello from print')
        """
        exe = self.compile(src)
        out = exe.run()
        assert out == "hello from print\n"

    def test_console_log(self):
        src = """
        from jsffi import init as js_init, get_Console

        def main() -> None:
            js_init()
            console = get_Console()
            console.log('hello from console.log')
            console.log(42)
        """
        exe = self.compile(src)
        out = exe.run()
        assert out == "hello from console.log\n42\n"

    def test_setattr(self):
        src = """
        from jsffi import init as js_init, get_Console, get_GlobalThis

        def main() -> None:
            js_init()
            globalThis = get_GlobalThis()
            console = get_Console()
            globalThis.xxx = "hello 1"
            console.log(globalThis.xxx)
            globalThis.xxx = "hello 2"
            console.log(globalThis.xxx)
        """
        exe = self.compile(src)
        out = exe.run()
        assert out == "hello 1\nhello 2\n"

    def test_callback(self):
        src = """
        from jsffi import init as js_init, get_GlobalThis

        def say_hello() -> None:
            print("hello from callback")

        def main() -> None:
            js_init()
            globalThis = get_GlobalThis()
            globalThis.setTimeout(say_hello) # XXX allow 2 params and pass 0
        """
        exe = self.compile(src)
        out = exe.run()
        assert out == "hello from callback\n"

    def test_call_method_0_1(self):
        src = """
        from jsffi import init as js_init, get_GlobalThis

        def main() -> None:
            js_init()
            globalThis = get_GlobalThis()
            arr = globalThis.Array()
            arr.push(42)
            result = arr.pop()
            globalThis.console.log(result)
        """
        exe = self.compile(src)
        out = exe.run()
        assert out == "42\n"

    def test_call_method_2(self):
        src = """
        from jsffi import init as js_init, get_GlobalThis

        def main() -> None:
            js_init()
            globalThis = get_GlobalThis()
            result = globalThis.Math.max(3, 7)
            globalThis.console.log(result)
        """
        exe = self.compile(src)
        out = exe.run()
        assert out == "7\n"

    def test_call_method_3(self):
        src = """
        from jsffi import init as js_init, get_GlobalThis

        def main() -> None:
            js_init()
            globalThis = get_GlobalThis()
            result = globalThis.Math.min(3, 7, 1)
            globalThis.console.log(result)
        """
        exe = self.compile(src)
        out = exe.run()
        assert out == "1\n"

    def test_call_method_4(self):
        src = """
        from jsffi import init as js_init, get_GlobalThis

        def main() -> None:
            js_init()
            globalThis = get_GlobalThis()
            globalThis.console.log(1, 2, 3, 4)
        """
        exe = self.compile(src)
        out = exe.run()
        assert out == "1 2 3 4\n"

    def test_call_method_5(self):
        src = """
        from jsffi import init as js_init, get_GlobalThis

        def main() -> None:
            js_init()
            globalThis = get_GlobalThis()
            globalThis.console.log(1, 2, 3, 4, 5)
        """
        exe = self.compile(src)
        out = exe.run()
        assert out == "1 2 3 4 5\n"

    def test_call_method_6(self):
        src = """
        from jsffi import init as js_init, get_GlobalThis

        def main() -> None:
            js_init()
            globalThis = get_GlobalThis()
            globalThis.console.log(1, 2, 3, 4, 5, 6)
        """
        exe = self.compile(src)
        out = exe.run()
        assert out == "1 2 3 4 5 6\n"

    def test_to_i32(self):
        src = """
        from jsffi import init as js_init, get_GlobalThis, js_to_i32

        def main() -> None:
            js_init()
            globalThis = get_GlobalThis()
            globalThis.testVal = 42
            ref = globalThis.testVal
            x: i32 = js_to_i32(ref)
            print(x)
        """
        exe = self.compile(src)
        out = exe.run()
        assert out == "42\n"

    def test_to_f64(self):
        src = """
        from jsffi import init as js_init, get_GlobalThis, js_to_f64

        def main() -> None:
            js_init()
            globalThis = get_GlobalThis()
            globalThis.testVal = 3.14
            ref = globalThis.testVal
            x: f64 = js_to_f64(ref)
            print(x)
        """
        exe = self.compile(src)
        out = exe.run()
        assert out == "3.14\n"

    def test_u8array_from_ptr(self):
        src = """
        from jsffi import init as js_init, get_GlobalThis, js_u8array_from_ptr
        from unsafe import gc_alloc

        def main() -> None:
            js_init()
            globalThis = get_GlobalThis()
            buf = gc_alloc[u8](12)
            arr = js_u8array_from_ptr(buf, 12)
            globalThis.console.log(arr.length)
        """
        exe = self.compile(src)
        out = exe.run()
        assert out == "12\n"

    def test_getDocument(self):
        src = """
        import jsffi

        def main() -> None:
            jsffi.init()
            globalThis = jsffi.get_GlobalThis()
            document = jsffi.get_Document()
            globalThis.console.log(document)
        """
        exe = self.compile(src)
        out = exe.run()
        # without browser, document is undefined
        assert out == "undefined\n"

    def test_request_animation_frame(self):
        src = """
        import jsffi

        def on_frame(time: f64) -> None:
            print(time)

        def main() -> None:
            jsffi.init()
            jsffi.request_animation_frame(on_frame)
        """
        exe = self.compile(src)
        # requestAnimationFrame is a browser API, so this cannot run
