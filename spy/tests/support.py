from typing import Any
import textwrap
import pytest
import spy.ast
from spy.parser import Parser
from spy.irgen.typechecker import TypeChecker
from spy.irgen.modgen import ModuleGen
from spy.errors import SPyCompileError
from spy.vm.vm import SPyVM
from spy.vm.module import W_Module

class CompilerPipeline:
    """
    Glue together all the various pieces which are necessary to compile a SPy
    module.

    By calling the appropriate methods, it is possible to run the compiler
    only up to a certain point, which is useful to inspect and test the
    individual steps.
    """
    vm: SPyVM
    srcfile: str
    parser: Parser
    mod: spy.ast.Module
    t: TypeChecker
    modgen: ModuleGen
    w_mod: W_Module

    def __init__(self, vm: SPyVM, srcfile: str) -> None:
        self.vm = vm
        self.srcfile = srcfile
        self.parser = None  # type: ignore
        self.mod = None     # type: ignore
        self.t = None       # type: ignore
        self.modgen = None  # type: ignore
        self.w_mod = None   # type: ignore

    def parse(self) -> spy.ast.Module:
        assert self.parser is None, 'parse() already called'
        self.parser = Parser.from_filename(str(self.srcfile))
        self.mod = self.parser.parse()
        return self.mod

    def typecheck(self) -> spy.ast.Module:
        assert self.t is None, 'typecheck() already called'
        self.parse()
        self.t = TypeChecker(self.vm, self.mod)
        self.t.check_everything()
        return self.mod

    def irgen(self) -> W_Module:
        assert self.modgen is None, 'irgen() already called'
        self.typecheck()
        self.modgen = ModuleGen(self.vm, self.t, self.mod)
        self.w_mod = self.modgen.make_w_mod()
        return self.w_mod

    ## def compile(self):
    ##     self.irgen()
    ##     ...


class AnyLocClass:
    def __eq__(self, other):
        return True
ANYLOC: Any = AnyLocClass()


@pytest.mark.usefixtures('init')
class CompilerTest:
    tmpdir: Any
    vm: SPyVM

    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir
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

    def _run_pipeline(self, src: str, stepname: str) -> Any:
        srcfile = self.write_source('test.py', src)
        self.compiler = CompilerPipeline(self.vm, srcfile)
        meth = getattr(self.compiler, stepname)
        return meth()

    def parse(self, src: str) -> spy.ast.Module:
        return self._run_pipeline(src, 'parse')

    def typecheck(self, src: str) -> spy.ast.Module:
        return self._run_pipeline(src, 'typecheck')

    def irgen(self, src: str) -> W_Module:
        return self._run_pipeline(src, 'irgen')

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
