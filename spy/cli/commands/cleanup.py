import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Optional, TypeGuard

from typer import Argument, BadParameter

from spy.cli._runners import Init_Args, init_vm
from spy.cli.commands.shared_args import Base_Args
from spy.util import cleanup_spyc_files


def path_optional_callback(value: Path) -> Path:
    """Check that the provided path is a directory, and show a nice error if not"""
    if value is not None and not Path(value).is_dir():
        raise BadParameter(
            f"--cleanup requires a directory argument, but {value} is not a directory"
        )
    return value


@dataclass
class Cleanup_Args(Base_Args):
    path: Annotated[
        Optional[Path],
        Argument(
            help="", callback=path_optional_callback, show_default="current directory"
        ),
    ] = None


async def cleanup(args: Cleanup_Args) -> None:
    """Remove .spyc cache files"""

    if args.path is None:
        paths = [os.getcwd()]
    else:
        paths = [str(args.path)]

    removed_count = cleanup_spyc_files(*paths)

    if not removed_count:
        print("No .spyc files found")
    else:
        print(f"2 {removed_count} file(s) removed")
