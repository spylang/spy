#!/usr/bin/env python3
"""Regenerate expected output files for all SPy examples.

Run this from anywhere; it always writes to examples/expected_output/.

    python examples/update_expected_output.py

After running, review the diff and commit the updated files.
"""

import subprocess
import sys
from pathlib import Path

EXAMPLES_DIR = Path(__file__).parent
EXPECTED_OUTPUT_DIR = EXAMPLES_DIR / "expected_output"


def expected_returncode(name: str) -> int:
    if name == "exit_code.spy":
        return 88
    return 0


def strip_comments(output: str) -> str:
    """Remove comment lines from captured output before comparison.

    Lines starting with '# ' are treated as volatile annotations (e.g. timing
    info) that the example intentionally prints but that should not be part of
    the stable expected output.
    """
    lines = [
        line for line in output.splitlines(keepends=True) if not line.startswith("# ")
    ]
    return "".join(lines)


def main() -> int:
    EXPECTED_OUTPUT_DIR.mkdir(exist_ok=True)

    spy_files = sorted(EXAMPLES_DIR.glob("*.spy"))
    if not spy_files:
        print("No .spy files found in", EXAMPLES_DIR)
        return 1

    updated = []
    errors = []
    for spy_file in spy_files:
        name = spy_file.name
        print(f"running {spy_file}")
        result = subprocess.run(
            ["spy", str(spy_file)],
            capture_output=True,
            text=True,
        )
        if result.returncode != expected_returncode(name):
            errors.append(spy_file.name)
            print(f"  FAILED  {spy_file.name}")
            print(f"    stderr: {result.stderr.strip()}")
            continue

        out_file = EXPECTED_OUTPUT_DIR / f"{spy_file.stem}.txt"

        result_to_be_saved = strip_comments(result.stdout)

        if out_file.exists() and out_file.read_text() != result_to_be_saved:
            updated.append(spy_file.name)
            out_file.write_text(result_to_be_saved)
            print(f"  updated  {out_file.relative_to(EXAMPLES_DIR)}")

    if errors:
        print(
            f"\n{len(errors)} example(s) failed and were not updated: {', '.join(errors)}"
        )
        return 1

    print(
        f"\nUpdated {len(updated)} file(s) in {EXPECTED_OUTPUT_DIR.relative_to(EXAMPLES_DIR)}/"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
