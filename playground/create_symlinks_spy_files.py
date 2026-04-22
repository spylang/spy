import tomllib
from pathlib import Path

path_playground = Path(__file__).parent.absolute()
path_examples = path_playground.parent / "examples"

with open("pyscript.toml", "rb") as f:
    config = tomllib.load(f)
EXAMPLE_FILES = [
    path_examples / source
    for source, dest in config.get("files", {}).items()
    if dest == "examples/"
]

for path_file in EXAMPLE_FILES:
    path_symlink = path_playground / path_file.name
    path_symlink.symlink_to(path_file)
