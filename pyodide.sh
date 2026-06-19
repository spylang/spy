#!/bin/sh

# Run python under pyodide-under-node, i.e. the same environment used by the
# web playground but without a browser. This is handy to reproduce and debug
# playground-specific behavior from the command line, e.g.:
#
#     ./pyodide.sh -m spy examples/1_high_level/hello.spy
#
# Requires ./pyodide/venv (see pyodide/README.md).

HERE=$(dirname "$0")
PYODIDE_PYTHON="$HERE/pyodide/venv/bin/python"

if [ ! -x "$PYODIDE_PYTHON" ]; then
    echo "Cannot find $PYODIDE_PYTHON" >&2
    echo "You need to create the pyodide venv first." >&2
    echo "See the instructions in $HERE/pyodide/README.md" >&2
    exit 1
fi

exec env -u PYTHONPATH "$PYODIDE_PYTHON" "$@"
