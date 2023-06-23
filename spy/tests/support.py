from typing import Any
import textwrap
import pytest
from spy.errors import SPyCompileError
from spy.vm.vm import SPyVM
from spy.util import Color

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

    def _do_expect_errors(self,
                          methname: str,
                          src: str, *,
                          errors: list[str]) -> SPyCompileError:
        """
        See TestParser.expect_errors and TestIRGen.expect_errors.
        """
        meth = getattr(self, methname)
        with pytest.raises(SPyCompileError) as exc:
            meth(src)
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
                expected = Color.set('yellow', expected)
                print('Error match failed!')
                print('The following error message was expected but not found:')
                print(f'  - {expected}')
                print()
                print('Captured error')
                formatted_error = err.format(use_colors=True)
                print(textwrap.indent(formatted_error, '    '))
                pytest.fail(f'Error message not found: {expected}')
