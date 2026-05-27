import os
import sys

IS_PYODIDE = "_pyodide_core" in sys.modules

if IS_PYODIDE:
    import js  # type: ignore

    IS_BROWSER = hasattr(js, "window")
    IS_NODE = hasattr(js, "process")
else:
    IS_BROWSER = False
    IS_NODE = False

IS_DOCS_BUILD = (docs_build := os.getenv("_SPY_DOCS_BUILD_ENV")) and int(
    docs_build
) == 1
