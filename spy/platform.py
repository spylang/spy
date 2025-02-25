import sys

IS_PYODIDE = "_pyodide_core" in sys.modules

if IS_PYODIDE:
    import js
    IS_BROWSER = hasattr(js, 'window')
    IS_NODE = hasattr(js, 'process')
else:
    IS_BROWSER = False
    IS_NODE = False
