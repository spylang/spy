import os
import pathlib

import pytest

from spy.tests.support import skip_if_emscripten

ROOT = pathlib.Path(__file__).parent.parent.parent


@pytest.mark.mypy
@skip_if_emscripten
def test_mypy():
    mypy_ini = ROOT.joinpath("mypy.ini")
    assert mypy_ini.exists()
    os.chdir(ROOT)
    os.environ["MYPY_FORCE_COLOR"] = "1"
    print()
    ret = os.system("mypy")
    print()
    if ret != 0:
        pytest.fail("mypy failed")
