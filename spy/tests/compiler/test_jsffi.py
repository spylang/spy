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
            print('hello')
        """)
        out = exe.run()
        assert out == 'hello\n'

    def test_console_log(self):
        exe = self.compile(
        """
        from jsffi import init as js_init, get_Console

        def main() -> void:
            js_init()
            console = get_Console()
            console.log('hello')
        """)
        out = exe.run()
        assert out == 'hello\n'
