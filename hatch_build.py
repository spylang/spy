"""
Build hook: compile libspy when the package is built.

  - wheel: build the prebuilt variant (wasi/debug-testlib, portable) and add it
    to the wheel as spy/libspy/prebuilt.
  - editable install (`uv sync`): nothing goes in the package; the standard
    variants are built into the user cache, so that pytest and spy find
    everything already built.
"""

import shutil
import sys
import sysconfig
import tempfile
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# no versions here (see CustomBuildHook.dependencies)
BUILD_DEPENDENCIES = {"ziglang", "ninja", "py", "platformdirs"}


def targets_emscripten() -> bool:
    """True when building for pyodide (e.g. `pip install .` in a pyodide venv)."""
    return sys.platform == "emscripten" or sysconfig.get_platform().startswith(
        "emscripten"
    )


class CustomBuildHook(BuildHookInterface):
    _tmp: Path | None = None

    def dependencies(self):
        # Not in `build-system.requires` because markers cannot express
        # "not targeting emscripten", see pyproject.toml.
        if self.target_name != "wheel" or targets_emscripten():
            return []
        return [
            str(req)
            for req in self.metadata.core.dependencies_complex.values()
            if req.name in BUILD_DEPENDENCIES
        ]

    def initialize(self, version, build_data):
        if self.target_name != "wheel":
            return
        if targets_emscripten():
            # Pyodide can't compile libspy: it uses the variants exported by
            # the host in spy/libspy/pyodide-libs (see pyodide/README.md).
            return
        # the project is not installed in the build environment
        sys.path.insert(0, self.root)
        import py.path

        from spy.libspy.builder import build_prebuilt, build_standard_variants

        if version == "editable":
            build_standard_variants()
        else:
            self._tmp = Path(tempfile.mkdtemp(prefix="spy-prebuilt-"))
            build_prebuilt(py.path.local(self._tmp))
            build_data["force_include"][str(self._tmp)] = "spy/libspy/prebuilt"

    def finalize(self, version, build_data, artifact_path):
        if self._tmp is not None:
            shutil.rmtree(self._tmp, ignore_errors=True)
