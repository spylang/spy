#!/usr/bin/env bash
# Local version of .github/workflows/test-wheel.yml: build the wheel, install
# it in a fresh venv and check that spy works from it.
#
# Usage: scripts/test-wheel.sh
#   KEEP_CACHE=1 scripts/test-wheel.sh   # don't clear the spy cache
#
# Needs uv and the libgc headers (libgc-dev on Debian/Ubuntu, bdw-gc with brew).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
VENV="$WORK/venv"

echo "==> Build wheel"
uv build --wheel --out-dir "$WORK/dist"

echo "==> Create venv and install the wheel"
uv venv "$VENV" --python 3.12
uv pip install --python "$VENV/bin/python" "$WORK"/dist/*.whl
export VIRTUAL_ENV="$VENV"
export PATH="$VENV/bin:$PATH"

echo "==> Check that spy comes from the wheel"
(
    cd "$WORK"
    which spy
    python -c "import spy; print(spy.__file__); assert 'site-packages' in spy.__file__"
)

if [ -z "${KEEP_CACHE:-}" ]; then
    # same location as spy.libspy.builder (SPY_CACHE_DIR or the user cache dir)
    CACHE_DIR="${SPY_CACHE_DIR:-$(python -c 'import platformdirs; print(platformdirs.user_cache_dir("spy"))')}"
    echo "==> Clear spy cache ($CACHE_DIR)"
    rm -rf "$CACHE_DIR"
fi

echo "==> Check spy commands"
(
    cd examples/1_high_level
    spy build hello.spy
    ./build/hello
    spy hello.spy
    spy build --target wasi hello.spy

    # --static is not supported on macOS
    if [ "$(uname)" = "Linux" ]; then
        spy build --static hello.spy
        ./build/hello
    fi
)

echo "==> Run examples tests"
uv pip install --python "$VENV/bin/python" pytest
(
    cd examples
    # -o addopts= because the addopts of pyproject.toml use an option
    # (--dist-dir) provided by pytest-pyodide, not installed in this venv
    pytest -o addopts= test_examples.py
)

echo "==> All checks passed"
