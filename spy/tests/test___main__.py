from typing import Any
import textwrap
import pytest
from typer.testing import CliRunner
from spy.__main__ import app


@pytest.mark.usefixtures('init')
class TestMain:
    tmpdir: Any

    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir
        self.runner = CliRunner()
        self.foo_spy = tmpdir.join('foo.spy')
        self.foo_spy.write(textwrap.dedent("""
        def add(x: i32, y: i32) -> i32:
            return x + y
        """))

    def run(self, *args: Any) -> None:
        args = [str(arg) for arg in args]
        print('run: spy %s' % ' '.join(args))
        res = self.runner.invoke(app, args)
        print(res.stdout)
        if res.exit_code != 0:
            raise res.exception
        return res

    def test_pyparse(self):
        res = self.run('--pyparse', self.foo_spy)
        assert 'py:Module' in res.stdout
