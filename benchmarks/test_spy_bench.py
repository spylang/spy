# type: ignore

import re
import subprocess
from pathlib import Path

import pytest

from spy.util import print_diff

BENCHMARKS_DIR = Path(__file__).parent
EXPECTED_OUTPUT_DIR = BENCHMARKS_DIR / "expected_output"

# Subdirectories that are not benchmarks and should never be validated.
_IGNORED_DIRS = {"expected_output", "__pycache__"}


def _subdirs() -> list[Path]:
    """All immediate subdirectories of benchmarks/, ignoring non-benchmark dirs."""
    return sorted(
        d
        for d in BENCHMARKS_DIR.iterdir()
        if d.is_dir() and d.name not in _IGNORED_DIRS
    )


def _makefile_has_target(makefile: Path, target: str) -> bool:
    return f"{target}:" in makefile.read_text()


def _benchmark_dirs_with_target(target: str) -> list[Path]:
    """Dirs that have a Makefile and declare the given target."""
    return [
        d
        for d in _subdirs()
        if (d / "Makefile").exists() and _makefile_has_target(d / "Makefile", target)
    ]


def test_benchmark_structure():
    """Every benchmark subdirectory must have a Makefile with both `test` and
    `check-ci` targets.

    This test collects all violations and reports them together so a developer
    adding a new benchmark sees everything that needs fixing in one go.

    Required layout for each benchmark dir:
      benchmarks/<name>/
        Makefile          # must exist
          test:           # runs only SPy, fast, no extra deps, output compared
          check-ci:       # runs all implementations available in CI
    """
    problems: list[str] = []

    for d in _subdirs():
        makefile = d / "Makefile"

        if not makefile.exists():
            problems.append(
                f"  {d.name}/: missing Makefile\n"
                f"    → Add a Makefile with at least `test` and `check-ci` targets."
            )
            continue  # no point checking targets if there's no Makefile

        missing_targets = [
            t for t in ("test", "check-ci") if not _makefile_has_target(makefile, t)
        ]
        if missing_targets:
            targets_str = " and ".join(f"`{t}`" for t in missing_targets)
            problems.append(
                f"  {d.name}/Makefile: missing {targets_str} target(s)\n"
                f"    → `test`     should run only SPy (fast, no extra deps).\n"
                f"    → `check-ci` should run all implementations available in CI."
            )

    if problems:
        joined = "\n".join(problems)
        pytest.fail(
            f"Found {len(problems)} benchmark(s) with structural problems:\n\n"
            f"{joined}\n\n"
            f"See benchmarks/README.md for the expected layout."
        )


# ---------------------------------------------------------------------------
# test_bench: run `make test` and compare against expected_output/
# ---------------------------------------------------------------------------

_test_dirs = _benchmark_dirs_with_target("test")


def _normalize_output(output: str) -> str:
    """Normalize captured output before comparison or saving.

    Two conventions are supported for volatile content (e.g. timing):

    - Lines starting with '#' are dropped entirely.
    - Within a line, everything from '#' to end-of-line is stripped.
      This handles the inline sentinel used by array benchmarks:
      e.g. `print("spy add:#", duration, "s")` → `spy add:` after stripping.

    Both conventions let benchmark code mark volatile timing output so the
    test framework can strip it while preserving the stable label prefix.
    """
    lines = []
    for line in output.splitlines(keepends=True):
        if line.startswith("#"):
            continue
        if "#" in line:
            line = re.sub(r"#.*", "", line).rstrip() + "\n"
        lines.append(line)
    return "".join(lines)


def _run_make_test(bench_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["make", "test"],
        cwd=bench_dir,
        capture_output=True,
        text=True,
        check=False,
    )


def test_all_benchmarks_have_expected_output(request):
    """Catch the case where a new benchmark was added without a saved expected output.

    Without this guard, test_bench would silently skip the new directory.
    Skipped when --update-expected-output is active because that mode creates the files.
    """
    if request.config.getoption("--update-expected-output"):
        pytest.skip("--update-expected-output will create any missing files")

    missing = [
        d for d in _test_dirs if not (EXPECTED_OUTPUT_DIR / f"{d.name}.txt").exists()
    ]
    if missing:
        names = "\n  ".join(d.name for d in missing)
        pytest.fail(
            f"Missing expected output for {len(missing)} benchmark(s):\n  {names}\n\n"
            f"Generate them with: pytest benchmarks/ --update-expected-output"
        )


@pytest.mark.parametrize("bench_dir", _test_dirs, ids=lambda d: d.name)
def test_bench(bench_dir: Path, request):
    """
    Run `make test` in each benchmark directory and compare stdout against
    the saved expected output in expected_output/<name>.txt.

    `make test` should run only the SPy implementation (fast, no extra
    dependencies), and its output should be deterministic modulo timing lines
    (which are filtered out via the `#` prefix or inline `#` convention).

    To regenerate expected output after an intentional change:
        pytest benchmarks/ --update-expected-output
    or for a single benchmark:
        pytest benchmarks/ --update-expected-output -k fibo
    """
    expected_file = EXPECTED_OUTPUT_DIR / f"{bench_dir.name}.txt"
    result = _run_make_test(bench_dir)

    if result.returncode != 0:
        pytest.fail(
            f"`make test` failed in {bench_dir.name}/\n\n"
            f"--- stdout ---\n{result.stdout}"
            f"--- stderr ---\n{result.stderr}"
        )

    normalized = _normalize_output(result.stdout)

    if request.config.getoption("--update-expected-output"):
        EXPECTED_OUTPUT_DIR.mkdir(exist_ok=True)
        expected_file.write_text(normalized)
        return

    assert expected_file.exists(), (
        f"No expected output for {bench_dir.name}. "
        f"Generate it with: pytest --update-expected-output -k {bench_dir.name}"
    )

    expected = expected_file.read_text()
    if normalized != expected:
        print_diff(expected, normalized, "expected", "got")
        pytest.fail(
            f"Output of {bench_dir.name} differs from "
            f"{expected_file.relative_to(BENCHMARKS_DIR)}\n\n"
            "Update the expected result with: pytest --update-expected-output"
        )
