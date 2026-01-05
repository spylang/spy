import textwrap
from contextlib import contextmanager
from typing import Any, Literal, Optional, no_type_check

import py.path
import pytest

from spy.backend.c.cbackend import CBackend
from spy.backend.interp import InterpModuleWrapper
from spy.build.config import BuildConfig, BuildTarget
from spy.build.ninja import NinjaWriter
from spy.doppler import ErrorMode
from spy.errors import SPyError
from spy.tests.cffi_wrapper import load_cffi_module
from spy.tests.exe_wrapper import ExeWrapper
from spy.tests.wasm_wrapper import WasmModuleWrapper
from spy.vm.vm import SPyVM

Backend = Literal["interp", "doppler", "C"]
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


def skip_backends(*backends_to_skip: Backend, reason=""):
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
            pytest.fail(f"Invalid backend passed to @skip_backends: {b}")

    new_backends = []
    for backend in ALL_BACKENDS:
        marks = [getattr(pytest.mark, backend)]
        if backend in backends_to_skip:
            marks.append(pytest.mark.skip(reason=reason))
        param = pytest.param(backend, marks=marks)
        new_backends.append(param)

    def decorator(func):
        return pytest.mark.parametrize("compiler_backend", new_backends)(func)

    return decorator


@no_type_check
def parametrize_compiler_backend(params, func):
    deco = pytest.mark.parametrize("compiler_backend", params_with_marks(params))
    return deco(func)


def no_backend(func):
    return parametrize_compiler_backend([""], func)


def only_interp(func):
    return parametrize_compiler_backend(["interp"], func)


def only_C(func):
    return parametrize_compiler_backend(["C"], func)


def only_emscripten(func):
    return parametrize_compiler_backend(["emscripten"], func)


def only_py_cffi(func):
    return parametrize_compiler_backend(["py-cffi"], func)


def no_C(func):
    return parametrize_compiler_backend(["interp", "doppler"], func)


@pytest.mark.usefixtures("init")
class CompilerTest:
    tmpdir: Any
    backend: Backend
    vm: SPyVM

    OPT_LEVEL: Optional[int] = None

    @pytest.fixture(params=params_with_marks(ALL_BACKENDS))  # type: ignore
    def compiler_backend(self, request):
        return request.param

    @pytest.fixture
    def init(self, request, tmpdir, compiler_backend):
        self.dump_c = request.config.getoption("--dump-c")
        self.dump_redshift = request.config.getoption("--dump-redshift")
        self.tmpdir = tmpdir
        self.builddir = self.tmpdir.join("build").ensure(dir=True)
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

    @property
    def error_reporting(self) -> str:
        # ideally for 'doppler' and 'C' we would like to be able to choose
        # either eager or lazy. For now, we hard-code it to eager.
        if self.backend == "interp":
            return "lazy"
        else:
            return "eager"

    # see test_backend_spy:test_zz_sanity_check for details
    SKIP_SPY_BACKEND_SANITY_CHECK = False
    ALL_COMPILED_SOURCES: set[str] = set()

    def compile(
        self,
        src: str,
        modname: str = "test",
        *,
        error_mode: ErrorMode = "eager",
    ) -> Any:
        """
        Compile the W_Module into something which can be accessed and called by
        tests.

        Depending on the `self.backend` value, it returns different objects. By default
        the following backends are supported:
        - `interp`: InterpModuleWrapper which, when called, runs the module in the
                    interpreter
        - `doppler`: Perform the redshift and then wraps the result in an
                     InterpModuleWrapper object.
        - `C`: compiles the module to C and then builds it to a WASM and wraps the
               result in a WasmModuleWrapper object.
        unless while using @only_emscripten decorator, in which case the following
        backend is used:
        - `emscripten`: compiles the module to C and then builds it to a JS
                        executable, wrapping the result in an ExeWrapper object.

        """
        self.write_file(f"{modname}.spy", src)
        self.w_mod = self.vm.import_(modname)
        if not self.SKIP_SPY_BACKEND_SANITY_CHECK:
            self.ALL_COMPILED_SOURCES.add(src)

        if self.backend == "":
            pytest.fail("Cannot call self.compile() on @no_backend tests")

        if self.backend == "interp":
            interp_mod = InterpModuleWrapper(self.vm, self.w_mod)
            return interp_mod

        # all backends apart 'interp' require redshifting
        self.vm.redshift(error_mode=error_mode)
        if self.dump_redshift:
            self.dump_module(modname)

        if self.backend == "doppler":
            interp_mod = InterpModuleWrapper(self.vm, self.w_mod)
            return interp_mod

        if self.backend == "C":
            config = BuildConfig(
                target="wasi",
                kind="lib",
                build_type="debug",
                opt_level=self.OPT_LEVEL,
            )
            WrapperClass = WasmModuleWrapper
        elif self.backend == "emscripten":
            config = BuildConfig(
                target="emscripten",
                kind="exe",
                build_type="debug",
                opt_level=self.OPT_LEVEL,
            )
            WrapperClass = ExeWrapper
        elif self.backend == "py-cffi":
            config = BuildConfig(
                target="native",
                kind="py-cffi",
                build_type="debug",
                opt_level=self.OPT_LEVEL,
            )
            WrapperClass = load_cffi_module
        else:
            assert False, f"Unknown backend: {self.backend}"

        backend = CBackend(self.vm, modname, config, self.builddir, dump_c=self.dump_c)
        backend.cwrite()
        backend.write_build_script()
        outfile = backend.build()  # e.g. 'test.wasm' or 'test.mjs'
        return WrapperClass(self.vm, modname, outfile)

    def dump_module(self, modname: str) -> None:
        from spy.cli._format import dump_spy_mod

        print()
        print()
        dump_spy_mod(self.vm, modname, full_fqn=False)

    def compile_raises(
        self,
        src: str,
        funcname: str,
        ctx: Any,
        *,
        modname: str = "test",
        error_reporting: Optional[str] = None,
    ) -> None:
        """
        Compile the given src and run the function with the given funcname.

        The code is expected to contains errors, but depending on the
        `error_reporting` mode, the error is raised at different times:

          - 'eager': the error is expected to be raised at compile-time

          - 'lazy': the error is expected to be raised at run-time

        `ctx` is a context manager which catches and expects the error, and is
        supposed to be obtained by calling `expect_errors`.
        """
        if error_reporting is None:
            error_reporting = self.error_reporting

        if error_reporting == "eager":
            with ctx:
                mod = self.compile(src, modname=modname)
        else:
            mod = self.compile(src)
            with ctx:
                fn = getattr(mod, funcname)
                fn()


MatchAnnotation = tuple[str, str]


@contextmanager
def expect_errors(main: str, *anns_to_match: MatchAnnotation) -> Any:
    """
    Similar to pytest.raises but:

      - expect a SPyError

      - check that the main error message matches

      - check that the given additional annotations match. For each
        annotation, you need to provide the message and the extract of source
        code which the annotation points to
    """
    with pytest.raises(SPyError) as exc:
        yield exc

    err = exc.value
    formatted_error = err.format(use_colors=True)
    formatted_error = textwrap.indent(formatted_error, "    ")

    def fail(msg: str, src: str):
        print("Error match failed!")
        print("The following message was expected but not found:")
        print(f"  - {msg}")
        if src:
            print(f"  - {src}")
        print()
        print("Captured error")
        print(formatted_error)
        pytest.fail(f"Error message not found: {msg}")

    def match_one_annotation(expected_msg: str, expected_src: str) -> bool:
        for ann in err.w_exc.annotations:
            got_src = ann.loc.get_src()
            if ann.message == expected_msg and expected_src == got_src:
                return True
        return False

    if err.w_exc.message != main:
        fail(main, "")

    for msg, src in anns_to_match:
        if not match_one_annotation(msg, src):
            fail(msg, src)

    print()
    print("The following error was expected (everything is good):")
    print(formatted_error)


@pytest.mark.usefixtures("init")
class CTest:
    tmpdir: Any
    target: BuildTarget

    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir
        # NOTE: target is overwritten by TestLLWasm.init_llwasm
        self.target = "wasi"
        self.build_dir = self.tmpdir.join("build").ensure(dir=True)

    def write(self, src: str) -> py.path.local:
        src = textwrap.dedent(src)
        test_c = self.tmpdir.join("test.c")
        test_c.write(src)
        return test_c

    def c_compile(self, src: str, *, exports: list[str] = []) -> py.path.local:
        config = BuildConfig(target=self.target, kind="lib", build_type="debug")
        test_c = self.write(src)
        ninja = NinjaWriter(config, self.build_dir)
        ninja.write("test", [test_c], wasm_exports=exports)
        return ninja.build()
