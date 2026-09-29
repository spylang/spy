# type: ignore

import subprocess
from pathlib import Path

import pytest

from spy.util import print_diff

EXAMPLES_DIR = Path(__file__).parent
EXPECTED_OUTPUT_DIR = EXAMPLES_DIR / "expected_output"

_spy_files = sorted(EXAMPLES_DIR.glob("[0-9]*/**/*.spy"))


def expected_returncode(path: Path) -> int:
    if path.name == "exit_code.spy":
        return 88
    return 0


def _normalize_output(output: str) -> str:
    """Normalize captured output before comparison or saving.

    Applies transformations to remove or replace volatile content:

    - Lines starting with '# ' are dropped entirely. Examples use this to print
      volatile annotations (e.g. timing) via `print("# " + str(elapsed))`.
    - The current working directory is replaced with '<CWD>' so that paths don't
      differ between machines.
    - Hexadecimal addresses (e.g. 0x1001460) are replaced with '<ADDR>' so that
      memory addresses in output don't cause spurious mismatches.
    """
    import re

    cwd = str(Path(__file__).absolute().parent)

    lines = []
    for line in output.splitlines(keepends=True):
        if line.startswith("# "):
            continue
        line = line.replace(cwd, "<CWD>")
        line = re.sub(r"0x[0-9a-fA-F]+", "<ADDR>", line)
        lines.append(line)

    return "".join(lines)


def _run(spy_file: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["spy", str(spy_file)],
        capture_output=True,
        text=True,
        check=False,
    )

def _build_run(spy_file: Path) -> subprocess.CompletedProcess:
    cmd = ["spy","build", str(spy_file)]
    subprocess.run(cmd)
    cmd = [str(spy_file.parent)+'/build/'+str(spy_file.stem)]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )

def test_all_examples_have_expected_output(request) -> None:
    """Catch the case where a new .spy file was added without a saved expected output.

    Without this guard, the parametrized test_example would simply not run for
    the new file, giving a false sense of coverage.
    Skipped when --update-examples is active because that mode creates the files.
    """
    if request.config.getoption("--update-examples"):
        pytest.skip("--update-examples will create any missing files")

    missing = [
        f for f in _spy_files if not (EXPECTED_OUTPUT_DIR / f"{f.stem}.txt").exists()
    ]
    if missing:
        names = "\n  ".join(f.name for f in missing)
        pytest.fail(
            f"Missing expected output for {len(missing)} example(s):\n  {names}\n\n"
            f"Generate them with: pytest --update-examples"
        )



def run_example(spy_file: Path, request,runner = _run) -> None:
    expected_file = EXPECTED_OUTPUT_DIR / f"{spy_file.stem}.txt"
    result = runner(spy_file)
    print(result.returncode,expected_returncode(spy_file))
    assert result.returncode == expected_returncode(spy_file), (
        f"spy exited with code {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}"
        f"--- stderr ---\n{result.stderr}"
    )

    if request.config.getoption("--update-examples"):
        EXPECTED_OUTPUT_DIR.mkdir(exist_ok=True)
        expected_file.write_text(_normalize_output(result.stdout))
        # A test must either pass or fail; we pass after a successful update.
        return

    assert expected_file.exists(), (
        f"No expected output for {spy_file.name}. "
        f"Generate it with: pytest --update-examples -k {spy_file.stem}"
    )

    expected = expected_file.read_text()
    normalize_output = _normalize_output(result.stdout)

    if normalize_output != expected:
        print_diff(expected, normalize_output, "expected", "got")
        pytest.fail(
            f"Output of {spy_file.name} differs from {expected_file.relative_to(EXAMPLES_DIR)}\n\n"
            "Update the expected result with: pytest --update-examples"
        )

@pytest.mark.parametrize("spy_file", _spy_files, ids=lambda f: f.stem)
def test_example_interp(spy_file: Path, request) -> None:
    run_example(spy_file,request)

@pytest.mark.parametrize("spy_file", _spy_files, ids=lambda f: f.stem)
def test_example_build(spy_file: Path, request) -> None:
    # There are four examples which fails in the c compiling stage - so they are marked as XFAIL
    if spy_file.stem in ['collections','annotated','unroll_nested_loops','convert']:
        pytest.xfail()
    run_example(spy_file,request,_build_run)
