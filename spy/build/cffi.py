import contextlib
import os
import sys
from pathlib import Path
from typing import Any

from spy.util import robust_run


@contextlib.contextmanager
def chdir(path: str | Path) -> Any:
    """Context manager to temporarily change directory."""
    old_dir = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(old_dir)


def cffi_build(build_script: Path) -> Path:
    """
    Generate a CPython extension module by running the cffi-build.py
    script produced by spy.backend.c.cffiwriter.
    """
    cmdline = [sys.executable, str(build_script)]
    d = build_script.parent
    with chdir(d):
        proc = robust_run(cmdline)
    # The generated .so file is expected to be in the stdout of the build script
    out = proc.stdout.decode("utf-8")
    sofile = Path(out.strip())
    assert sofile.exists()
    return sofile
