# type: ignore

import shutil
import sys

import py
import pytest
from pytest_pyodide import get_global_config

from spy.util import cleanup_spyc_files

ROOT = py.path.local(__file__).dirpath()
HAVE_EMCC = shutil.which("emcc") is not None


@pytest.hookimpl
def pytest_collection_modifyitems(session, config, items):
    """
    Reorder the test to have a "better" order. In particular:

      - test_zz_mypy.py is always the last, after the subdirectories
      - tests in the root tests/ directory run before tests in subdirectories
      - tests directly in a directory run before tests in its subdirectories
    """

    def key(item):
        filename = item.fspath.relto(ROOT)

        # very slow tests always run last
        if filename == "test_zz_mypy.py":
            return (100, 0)  # last
        elif filename == "test_cli.py":
            return (98, 0)
        elif filename == "test_llwasm.py":
            return (97, 0)

        # Check for markers and assign priority
        if item.get_closest_marker("emscripten") or item.get_closest_marker("pyodide"):
            marker_priority = 90
        elif item.get_closest_marker("C"):
            marker_priority = 80
        elif item.get_closest_marker("doppler"):
            marker_priority = 70
        elif item.get_closest_marker("interp"):
            marker_priority = 60
        else:
            marker_priority = 0

        # Sort by directory depth (fewer slashes = higher priority)
        depth = filename.count("/")
        return (marker_priority, depth)

    items.sort(key=key)


def pytest_addoption(parser):
    parser.addoption(
        "--dump-c", action="store_true", default=False, help="Dump generated C code"
    )
    parser.addoption(
        "--dump-redshift",
        action="store_true",
        default=False,
        help="Dump the redshifted module",
    )
    parser.addoption(
        "--spdb", action="store_true", default=False, help="Enter SPdb on errors"
    )
    parser.addoption(
        "--cleanup",
        action="store_true",
        default=False,
        help="Remove all .spyc cache files from stdlib before running tests",
    )


@pytest.fixture(autouse=True)
def skip_if_no_emcc(request):
    if request.node.get_closest_marker("emscripten") and not HAVE_EMCC:
        pytest.skip("Requires emcc")


@pytest.fixture(scope="session", autouse=True)
def cleanup_spyc_files_fixture(request):
    """
    Remove all .spyc cache files from stdlib if --cleanup option is used.
    """
    if request.config.getoption("--cleanup"):
        stdlib_dir = ROOT.join("..", "..", "stdlib")
        if stdlib_dir.check(dir=True):
            cleanup_spyc_files(stdlib_dir)


@pytest.fixture(scope="session", autouse=True)
def spy_backend_sanity_check_fixture(tmpdir_factory):
    """
    Run SPy backend sanity check at the end of the test session.

    This ensures that the SPy backend can format all AST nodes that were
    compiled during the test run. This runs on every xdist worker.
    """
    from spy.tests.test_backend_spy import run_sanity_check_fixture

    yield
    run_sanity_check_fixture(tmpdir_factory)


# ===============
# pyodide config
# ===============


def call_immediately(f):
    f()
    return f


@call_immediately
def configure_pyodide():
    SPY_ROOT = ROOT.join("..", "..")  # the root of the repo

    pytest_pyodide_config = get_global_config()
    pytest_pyodide_config.set_flags(
        "node",
        pytest_pyodide_config.get_flags("node")
        + ["--experimental-wasm-stack-switching"],
    )
    pytest_pyodide_config.set_load_pyodide_script(
        "node",
        """
        let pyodide = await loadPyodide({
            fullStdLib: false,
            enableRunUntilComplete: true,
        });
        await pyodide.loadPackage(["pytest", "typing-extensions"]);
        """,
    )
    pytest_pyodide_config.set_initialize_script(
        f"""
        pyodide.mountNodeFS("{SPY_ROOT}", "{SPY_ROOT}");
        pyodide.runPython("import sys; sys.path.append('{SPY_ROOT}')");
        """
    )
