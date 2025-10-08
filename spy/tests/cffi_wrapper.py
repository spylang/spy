from typing import Any
import sys
import py.path
from spy.vm.vm import SPyVM


def isolated_import(modname: str, sofile: py.path.local):
    """
    Import the given modules in isolation, without leaving trace in
    sys.modules
    """
    assert modname not in sys.modules
    before_mods = set(sys.modules.keys())

    d = sofile.dirpath()
    sys.path.insert(0, str(d))
    try:
        mod = __import__(modname)
    finally:
        sys.path.pop(0)

    assert modname in sys.modules
    after_mods = set(sys.modules.keys())
    new_mods = after_mods - before_mods - {"_cffi_backend"}
    for modname in new_mods:
        del sys.modules[modname]

    return mod


def load_cffi_module(vm: SPyVM, modname: str, sofile: py.path.local) -> Any:
    return isolated_import(modname, sofile)
