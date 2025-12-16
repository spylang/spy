import os
from dataclasses import dataclass

from spy.cli.base_args import (
    Base_Args,
    Filename_Optional_Args,
)
from spy.cli.support import init_vm
from spy.util import (
    cleanup_spyc_files,
)


@dataclass
class Cleanup_Args(Base_Args, Filename_Optional_Args): ...


async def cleanup(args: Cleanup_Args) -> None:
    """Remove .spyc cache files from the provided path or cwd if vm is None)"""
    if args.filename:
        vm = await init_vm(
            args
        )  # TODO There's a type error here - we know args.filename is not None but mypy can't infer that for some reason
    else:
        vm = None
    paths = vm.path if vm is not None else [os.getcwd()]
    _do_cleanup(paths)


def _do_cleanup(paths: list[str]) -> None:
    removed_count = cleanup_spyc_files(paths)

    if removed_count == 0:
        print("No .spyc files found")
    else:
        print(f"Removed {removed_count} .spyc file(s)")
