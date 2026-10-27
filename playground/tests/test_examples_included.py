"""
Check that every .spy file living in a numbered examples/ subdirectory
(e.g. examples/1_high_level, examples/2_metaprogramming, ...) is listed in
playground/pyscript.toml, so that it actually gets shipped to the playground.
"""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = ROOT / "examples"
PYSCRIPT_TOML = ROOT / "playground" / "pyscript.toml"


def numbered_example_spy_files():
    files = set()
    for subdir in EXAMPLES_DIR.iterdir():
        if subdir.is_dir() and subdir.name[0].isdigit():
            for spy_file in subdir.glob("*.spy"):
                files.add(spy_file.relative_to(ROOT))
    return files


def spy_files_in_pyscript_toml():
    with PYSCRIPT_TOML.open("rb") as f:
        data = tomllib.load(f)

    files = set()
    for key in data.get("files", {}):
        if key.startswith("./examples/") and key.endswith(".spy"):
            files.add(Path(key[len("./") :]))
    return files


def test_examples_included():
    on_disk = numbered_example_spy_files()
    in_toml = spy_files_in_pyscript_toml()

    missing = on_disk - in_toml
    assert not missing, (
        f"The following .spy files are missing from "
        f"{PYSCRIPT_TOML.relative_to(ROOT)}: "
        f"{sorted(str(p) for p in missing)}"
    )
