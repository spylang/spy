from typing import Any
import sys
import os
import py.path
import contextlib
from spy.util import robust_run

@contextlib.contextmanager
def chdir(path: str|py.path.local) -> Any:
    """Context manager to temporarily change directory."""
    old_dir = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(old_dir)


def cffi_build(build_script: py.path.local) -> py.path.local:
    """
    Generate a CPython extension module by running the cffi-build.py
    script produced by spy.backend.c.cffiwriter.
    """
    cmdline = [sys.executable, str(build_script)]
    d = build_script.dirpath()
    with chdir(d):
        proc = robust_run(cmdline)
    out = proc.stdout.decode('utf-8')
    sofile = py.path.local(out.strip())
    assert sofile.exists()
    return sofile
