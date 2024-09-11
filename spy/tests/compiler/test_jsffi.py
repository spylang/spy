#-*- encoding: utf-8 -*-

import pytest
from spy.libspy import SPyPanicError
from spy.tests.support import CompilerTest, skip_backends, only_emscripten

@only_emscripten
class TestJsFFI(CompilerTest):

    def test_emscripten_run(self):
        exe = self.compile(
        """
        def main() -> void:
            print('hello from print')
        """)
        out = exe.run()
        assert out == 'hello from print\n'

    def test_console_log(self):
        exe = self.compile(
        """
        from jsffi import init as js_init, get_Console

        def main() -> void:
            js_init()
            console = get_Console()
            console.log('hello from console.log')
            console.log(42)
        """)
        out = exe.run()
        assert out == 'hello from console.log\n42\n'

    @pytest.mark.skip(reason="missing type conversions")
    def test_setattr(self):
        exe = self.compile(
        """
        from jsffi import init as js_init, get_Console, get_GlobalThis

        def main() -> void:
            js_init()
            globalThis = get_GlobalThis()
            console = get_Console()
            globalThis.xxx = "hello 1"
            console.log(globalThis.xxx)
            globalThis.xxx = "hello 2"
            console.log(globalThis.xxx)
        """)
        out = exe.run()
        assert out == 'hello 1\nhello 2\n'

    def test_callback(self):
        exe = self.compile(
        """
        from jsffi import init as js_init, get_GlobalThis

        def say_hello() -> void:
            print("hello from callback")

        def main() -> void:
            js_init()
            globalThis = get_GlobalThis()
            globalThis.setTimeout(say_hello) # XXX allow 2 params and pass 0
        """)
        out = exe.run()
        assert out == 'hello from callback\n'
