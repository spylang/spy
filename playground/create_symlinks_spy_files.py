import tomllib
from pathlib import Path

path_playground = Path(__file__).parent.absolute()
path_root = path_playground.parent

with open(path_playground / "pyscript.toml", "rb") as f:
    config = tomllib.load(f)
EXAMPLE_FILES = [
    path_root / loc / source
    for source, loc in config.get("files", {}).items()
    if loc.startswith("examples/")
]

print(EXAMPLE_FILES)

for path_file in EXAMPLE_FILES:
    path_symlink = path_playground / path_file.name
    path_symlink.symlink_to(path_file)
