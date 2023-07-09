from typing import Any, Literal
import textwrap
import pytest
import spy.ast
from spy.compiler import CompilerPipeline
from spy.backend.interp import InterpModuleWrapper
from spy.backend.c.wrapper import WasmModuleWrapper
from spy.errors import SPyCompileError
from spy.vm.vm import SPyVM
from spy.vm.module import W_Module

Backend = Literal['interp', 'C']
ALL_BACKENDS = Backend.__args__  # type: ignore

def params_with_marks(params):
    """
    Small helper to automatically apply to each param a pytest.mark with the
    same name of the param itself. E.g.:

        params_with_marks(['aaa', 'bbb'])

    is equivalent to:

        [pytest.param('aaa', marks=pytest.mark.aaa),
         pytest.param('bbb', marks=pytest.mark.bbb)]

    This makes it possible to use 'pytest -m aaa' to run ONLY the tests which
    uses the param 'aaa'.
    """
    return [pytest.param(name, marks=getattr(pytest.mark, name)) for name in params]

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
        marks = [getattr(pytest.mark, backend)]
        if backend in backends_to_skip:
            marks.append(pytest.mark.skip(reason=reason))
        param = pytest.param(backend, marks=marks)
        new_backends.append(param)

    def decorator(func):
        return pytest.mark.parametrize('compiler_backend', new_backends)(func)
    return decorator

def no_backend(func):
    return pytest.mark.parametrize('compiler_backend', [''])(func)


@pytest.mark.usefixtures('init')
class CompilerTest:
    tmpdir: Any
    backend: Backend
    vm: SPyVM
    compiler: CompilerPipeline

    @pytest.fixture(params=params_with_marks(ALL_BACKENDS))  # type: ignore
    def compiler_backend(self, request):
        return request.param

    @pytest.fixture
    def init(self, tmpdir, compiler_backend):
        self.tmpdir = tmpdir
        self.builddir = self.tmpdir.join('build').ensure(dir=True)
        self.backend = compiler_backend
        self.vm = SPyVM()
        self.compiler = None  # type: ignore

    def new_compiler(self, src: str):
        srcfile = self.write_file('test.spy', src)
        self.compiler = CompilerPipeline(self.vm, srcfile, self.builddir)

    def write_file(self, filename: str, src: str) -> Any:
        """
        Write the give source code to the specified filename, in the tmpdir.

        The source code is automatically dedented.
        """
        src = textwrap.dedent(src)
        srcfile = self.tmpdir.join(filename)
        srcfile.write(src)
        return srcfile

    def parse(self, src: str) -> spy.ast.Module:
        self.new_compiler(src)
        return self.compiler.parse()

    def compile(self, src: str) -> Any:
        """
        Compile the W_Module into something which can be accessed and called by
        tests.

        Currently, the only support backend is 'interp', which is a fake
        backend: the IR code is not compiled and function are executed by the
        VM.
        """
        self.new_compiler(src)
        if self.backend == '':
            pytest.fail('Cannot call self.compile() on @no_backend tests')
        elif self.backend == 'interp':
            w_mod = self.compiler.irgen()
            interp_mod = InterpModuleWrapper(self.vm, w_mod)
            return interp_mod
        elif self.backend == 'C':
            file_wasm = self.compiler.cbuild()
            return WasmModuleWrapper(file_wasm)
        else:
            assert False, f'Unknown backend: {self.backend}'

    def expect_errors(self, src: str, *,
                      errors: list[str],
                      stepname: str = 'irgen') -> SPyCompileError:
        """
        Expect that compilation fails, and check that the expected errors are
        reported
        """
        self.new_compiler(src)
        meth = getattr(self.compiler, stepname)
        with pytest.raises(SPyCompileError) as exc:
            meth()
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
