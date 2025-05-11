import sys
import os
import importlib.util
import sysconfig
import py.path
from spy.vm.vm import SPyVM

def import_sofile(path):
    """
    Import a .so extension module from an arbitrary path,
    using the correct module name by stripping the ABI tag.

    Args:
        path (str): Path to the .so file.

    Returns:
        module: The imported Python extension module.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"No such file: '{path}'")
    if not path.endswith(".so"):
        raise ValueError(f"Expected a .so file, got: '{path}'")

    abi_tag = sysconfig.get_config_var("SOABI")  # e.g., cpython-312-x86_64-linux-gnu
    filename = os.path.basename(path)

    suffix = f".{abi_tag}.so"
    if not filename.endswith(suffix):
        raise ImportError(f"Expected filename to end with '{suffix}', got '{filename}'")

    module_name = filename[: -len(suffix)]

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create a spec for module from: '{path}'")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CFFIWrapper:

    def __init__(self, vm: SPyVM, modname: str, sofile: py.path.local) -> None:
        self.vm = vm
        self.modname = modname
        self.sofile = sofile
        self.pymod = import_sofile(str(sofile))

    def __repr__(self) -> str:
        return f"<CFFIWrapper '{self.modname}' ({self.sofile})>"
