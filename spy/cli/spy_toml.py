"""
Reader for spy.toml project manifests.

spy.toml is an optional file that lives next to the entry-point .spy file.
It declares project-level settings, most importantly out-of-tree builtin
modules to load before running or compiling the program.

Example spy.toml:
    extra-vm-modules = [
        "../mymod",
    ]

Paths are relative to the directory that contains spy.toml.
"""

import tomllib  # stdlib since Python 3.11
from pathlib import Path
from typing import Optional


class SpyToml:
    path: Path
    extra_vm_modules: list[str]

    def __init__(self, path: Path, *, extra_vm_modules: list[str] = []) -> None:
        self.path = path
        self.extra_vm_modules = list(extra_vm_modules)

    @classmethod
    def find_and_read(cls, srcdir: Path) -> "SpyToml":
        """
        Look for spy.toml in srcdir. If not found, return an empty SpyToml.
        Paths in the file are resolved relative to spy.toml's directory.
        """
        toml_path = srcdir / "spy.toml"
        if not toml_path.exists():
            return cls(toml_path)

        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        raw_mods: list[str] = data.get("extra-vm-modules", [])
        toml_dir = toml_path.parent
        resolved = [str((toml_dir / m).resolve()) for m in raw_mods]
        return cls(toml_path, extra_vm_modules=resolved)

    def merge(self, cli_extra_vm_modules: Optional[list[str]]) -> list[str]:
        """
        Return the combined list of extra-vm-module paths, with CLI flags
        appended after the spy.toml entries.
        """
        result = list(self.extra_vm_modules)
        if cli_extra_vm_modules:
            result += cli_extra_vm_modules
        return result
