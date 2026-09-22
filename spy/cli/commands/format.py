import sys
from dataclasses import dataclass
from pathlib import Path

from typer import Argument

from spy.analyze.importing import ImportAnalyzer
from spy.cli._runners import init_vm
from spy.cli.commands.shared_args import Base_Args
from spy.tool.spyformatter import SPyFormatter


@dataclass
class Fmt_Args(Base_Args):
    filename: Path = Argument(help="", show_default=False)


async def format(args: Fmt_Args) -> None:
    """Format SPy file"""
    # TODO: implement directory formatting.
    if args.filename.suffix != ".spy":
        print(
            f"Error: {args.filename} is not a .spy file or directory.",
            file=sys.stderr,
        )
        sys.exit(1)

    formatter = SPyFormatter()
    formatter.format(args.filename)
