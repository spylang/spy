from typing import Any, Literal, Optional
import textwrap
from contextlib import contextmanager
import pytest
import py.path
import spy.ast
from spy.compiler import Compiler
from spy.backend.interp import InterpModuleWrapper
from spy.backend.c.wrapper import WasmModuleWrapper
from spy.cbuild import ZigToolchain
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
    return [pytest.param(name, marks=getattr(pytest.mark, name))
            for name in params]

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
2    """
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

    @pytest.fixture(params=params_with_marks(ALL_BACKENDS))  # type: ignore
    def compiler_backend(self, request):
        return request.param

    @pytest.fixture
    def init(self, tmpdir, compiler_backend):
        self.tmpdir = tmpdir
        self.builddir = self.tmpdir.join('build').ensure(dir=True)
        self.backend = compiler_backend
        self.vm = SPyVM()
        self.vm.path.append(str(self.tmpdir))

    def write_file(self, filename: str, src: str) -> Any:
        """
        Write the give source code to the specified filename, in the tmpdir.

        The source code is automatically dedented.
        """
        src = textwrap.dedent(src)
        srcfile = self.tmpdir.join(filename)
        srcfile.write(src)
        return srcfile

    def compile(self, src: str) -> Any:
        """
        Compile the W_Module into something which can be accessed and called by
        tests.

        Currently, the only support backend is 'interp', which is a fake
        backend: the IR code is not compiled and function are executed by the
        VM.
        """
        modname = 'test'
        self.write_file(f'{modname}.spy', src)
        self.irgen = self.vm.run_irgen(modname)
        if self.backend == '':
            pytest.fail('Cannot call self.compile() on @no_backend tests')
        elif self.backend == 'interp':
            interp_mod = InterpModuleWrapper(self.vm, self.irgen.w_mod)
            return interp_mod
        elif self.backend == 'C':
            compiler = Compiler(self.vm, modname, self.builddir)
            file_wasm = compiler.cbuild()
            return WasmModuleWrapper(self.vm, modname, file_wasm)
        else:
            assert False, f'Unknown backend: {self.backend}'


    def get_funcdef(self, name: str) -> spy.ast.FuncDef:
        """
        Search for the spy.ast.FuncDef with the given name in the parsed module
        """
        for decl in self.irgen.mod.decls:
            if isinstance(decl, spy.ast.FuncDef) and decl.name == name:
                return decl
        raise KeyError(name)

    def expect_errors(self, src: str, *, errors: list[str]):
        """
        Expect that compilation fails, and check that the expected errors are
        reported
        """
        modname = 'test'
        srcfile = self.write_file(f'{modname}.spy', src)
        with expect_errors(errors):
            self.vm.import_(modname)



@contextmanager
def expect_errors(errors: list[str]) -> Any:
    """
    Similar to pytest.raises but:

      - expect a SPyCompileError
      - check that the given messages are present in the error, either as
        the main message or in the annotations.
    """
    with pytest.raises(SPyCompileError) as exc:
        yield

    err = exc.value
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



@pytest.mark.usefixtures('init')
class CTest:
    tmpdir: Any

    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir
        self.toolchain = ZigToolchain()
        self.builddir = self.tmpdir.join('build').ensure(dir=True)


    def compile(self, src: str, *,
                exports: Optional[list[str]] = None) -> py.path.local:
        src = textwrap.dedent(src)
        test_c = self.tmpdir.join('test.c')
        test_c.write(src)
        test_wasm = self.builddir.join('test.wasm')
        self.toolchain.c2wasm(test_c, test_wasm, exports=exports)
        return test_wasm
