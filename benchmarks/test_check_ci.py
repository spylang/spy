# type: ignore

import subprocess
from pathlib import Path

import pytest

BENCHMARKS_DIR = Path(__file__).parent
_IGNORED_DIRS = {"expected_output", "__pycache__"}


def _benchmark_dirs_with_target(target: str) -> list[Path]:
    return sorted(
        d
        for d in BENCHMARKS_DIR.iterdir()
        if d.is_dir()
        and d.name not in _IGNORED_DIRS
        and (d / "Makefile").exists()
        and f"{target}:" in (d / "Makefile").read_text()
    )


_check_ci_dirs = _benchmark_dirs_with_target("check-ci")


@pytest.mark.parametrize("bench_dir", _check_ci_dirs, ids=lambda d: d.name)
def test_check_ci(bench_dir):
    """
    Run `make check-ci` in each benchmark directory.

    This target is intended for CI and runs all implementations available in
    the CI environment (Julia, Codon, PyPy, SPy, ...). The test passes if
    make exits with code 0.

    Dependencies (Julia, Codon, PyPy via uv) must be installed; see
    benchmarks/README.md.

    Note: structural checks (missing Makefile, missing targets) are handled
    by test_benchmark_structure() in test_bench.py and are not repeated here.
    """
    result = subprocess.run(
        ["make", "check-ci"],
        cwd=bench_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            f"`make check-ci` failed in {bench_dir.name}/\n\n"
            f"--- stdout ---\n{result.stdout}"
            f"--- stderr ---\n{result.stderr}"
        )
