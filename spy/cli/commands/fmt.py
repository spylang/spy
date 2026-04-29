import sys
from dataclasses import dataclass
from pathlib import Path

from typer import Argument

from spy.analyze.fmt import SPyFormatter
from spy.cli._runners import init_vm
from spy.cli.commands.shared_args import Base_Args


@dataclass
class Fmt_Args(Base_Args):
    filename: Path = Argument(help="", show_default=False)


async def fmt(args: Fmt_Args) -> None:
    """Format SPy file or directory"""
    if args.filename.suffix != ".spy":
        print(
            f"Error: {args.filename} is not a .spy file or directory.",
            file=sys.stderr,
        )
        sys.exit(1)

    vm = await init_vm(args)
    formatter = SPyFormatter(vm)
    formatter.format(args.filename.stem)
