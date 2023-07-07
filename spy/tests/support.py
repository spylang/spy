from typing import Any
import textwrap
import pytest
import spy.ast
from spy.compiler import CompilerPipeline, Backend
from spy.errors import SPyCompileError
from spy.vm.vm import SPyVM
from spy.vm.module import W_Module

ALL_BACKENDS = Backend.__args__  # type: ignore

def skip_backends(*backends_to_skip: Backend, reason=''):
    """
    Decorator to skip tests only for certain backends. Can be used to decorate
    classes or functions.

    Examples:

        @skip_backends('C')
        class TestXXX(CompilerTest):
            ...

        class TestYYY(CompilerTest):
            @skip_backends('C', reason='FIXME')
            def test_something(self):
                ...
    """
    for b in backends_to_skip:
        if b not in ALL_BACKENDS:
            pytest.fail(f'Invalid backend passed to @skip_backends: {b}')

    new_backends = []
    for backend in ALL_BACKENDS:
        if backend in backends_to_skip:
            backend = pytest.param(backend, marks=pytest.mark.skip(reason=reason))
        new_backends.append(backend)

    def decorator(func):
        return pytest.mark.parametrize('compiler_backend', new_backends)(func)
    return decorator


@pytest.mark.usefixtures('init')
class CompilerTest:
    tmpdir: Any
    backend: Backend
    vm: SPyVM

    @pytest.fixture(params=ALL_BACKENDS)
    def compiler_backend(self, request):
        return request.param

    @pytest.fixture
    def init(self, tmpdir, compiler_backend):
        self.tmpdir = tmpdir
        self.backend = compiler_backend
        self.vm = SPyVM()

    def write_source(self, filename: str, src: str) -> Any:
        """
        Write the give source code to the specified filename, in the tmpdir.

        The source code is automatically dedented.
        """
        src = textwrap.dedent(src)
        srcfile = self.tmpdir.join(filename)
        srcfile.write(src)
        return srcfile

    def _run_pipeline(self, src: str, stepname: str, **kwargs: Any) -> Any:
        srcfile = self.write_source('test.py', src)
        self.compiler = CompilerPipeline(self.vm, self.backend, srcfile)
        meth = getattr(self.compiler, stepname)
        return meth(**kwargs)

    def parse(self, src: str) -> spy.ast.Module:
        return self._run_pipeline(src, 'parse')

    def typecheck(self, src: str) -> spy.ast.Module:
        return self._run_pipeline(src, 'typecheck')

    def irgen(self, src: str) -> W_Module:
        return self._run_pipeline(src, 'irgen')

    def compile(self, src: str) -> Any:
        return self._run_pipeline(src, 'compile', backend=self.backend)

    def expect_errors(self,src: str, *,
                      errors: list[str],
                      stepname: str = 'irgen') -> SPyCompileError:
        """
        Expect that compilation fails, and check that the expected errors are
        reported
        """
        with pytest.raises(SPyCompileError) as exc:
            self._run_pipeline(src, stepname)
        err = exc.value
        self.assert_messages(err, errors=errors)
        return err

    def assert_messages(self, err: SPyCompileError, *, errors: list[str]) -> None:
        """
        Check whether all the given messages are present in the error, either as
        the main message or in the annotations.
        """
        all_messages = [err.message] + [ann.message for ann in err.annotations]
        for expected in errors:
            if expected not in all_messages:
                print('Error match failed!')
                print('The following error message was expected but not found:')
                print(f'  - {expected}')
                print()
                print('Captured error')
                formatted_error = err.format(use_colors=True)
                print(textwrap.indent(formatted_error, '    '))
                pytest.fail(f'Error message not found: {expected}')
