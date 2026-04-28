import subprocess
from pathlib import Path

import pytest
from update_expected_output import expected_returncode, strip_comments

EXAMPLES_DIR = Path(__file__).parent
EXPECTED_OUTPUT_DIR = EXAMPLES_DIR / "expected_output"

_spy_files = sorted(EXAMPLES_DIR.glob("*.spy"))


def _missing_expected_output() -> list[Path]:
    """Return spy files that have no corresponding expected output file."""
    return [
        f for f in _spy_files if not (EXPECTED_OUTPUT_DIR / f"{f.stem}.txt").exists()
    ]


def test_all_examples_have_expected_output() -> None:
    """Catch the case where a new .spy file was added without a saved expected output.

    Without this, the parametrized test below would simply not run for the new
    file, giving a false sense of coverage.
    """
    missing = _missing_expected_output()
    if missing:
        names = "\n  ".join(f.name for f in missing)
        pytest.fail(
            f"Missing expected output for {len(missing)} example(s):\n  {names}\n\n"
            f"Generate them by running update_expected_output.py from the examples/ directory."
        )


@pytest.mark.parametrize("spy_file", _spy_files, ids=lambda f: f.stem)
def test_example(spy_file: Path) -> None:
    expected_file = EXPECTED_OUTPUT_DIR / f"{spy_file.stem}.txt"
    if not expected_file.exists():
        pytest.skip(f"No expected output for {spy_file.name}")

    result = subprocess.run(
        ["spy", str(spy_file)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == expected_returncode(spy_file.name), (
        f"spy exited with code {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}"
        f"--- stderr ---\n{result.stderr}"
    )
    assert _strip_comments(result.stdout) == _strip_comments(
        expected_file.read_text()
    ), (
        f"Output of {spy_file.name} differs from {expected_file.relative_to(EXAMPLES_DIR)}"
    )
