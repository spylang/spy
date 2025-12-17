import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Optional, TypeGuard

from typer import Argument, BadParameter

from spy.cli._runners import Init_Args, init_vm
from spy.cli.commands.base_args import Base_Args
from spy.util import cleanup_spyc_files


def filename_optional_callback(value: Path) -> Path:
    if value is not None and not Path(value).is_dir():
        raise BadParameter(
            f"--cleanup requires a directory argument, but {value} is not a directory"
        )
    return value


@dataclass
class Cleanup_Args(Base_Args):
    filename: Annotated[
        Optional[Path],
        Argument(help=""),
    ] = None


async def cleanup(args: Cleanup_Args) -> None:
    """Remove .spyc cache files from the provided path or cwd no file is provided"""

    def guard_Init_Args(val: Any) -> TypeGuard[Init_Args]:
        # Determine if a filename was provided in a typesafe way
        return val.filename is not None

    if guard_Init_Args(args):
        vm = await init_vm(args)
        paths = vm.path
        print(f"vm paths = {paths}")
    else:
        paths = [os.getcwd()]

    removed_count = cleanup_spyc_files(*paths)

    if not removed_count:
        print("No .spyc files found")
    else:
        print(f"Removed {removed_count} .spyc file(s)")
