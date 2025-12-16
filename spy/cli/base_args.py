from dataclasses import dataclass
from pathlib import Path
from typing import (
    Annotated,
    Optional,
)

import click
from typer import Argument, Option

from spy.doppler import ErrorMode
from spy.vm.vm import SPyVM

GLOBAL_VM: Optional[SPyVM] = None


@dataclass
class Base_Args:
    """These arguments can be applied to any spy command/subcommand"""

    timeit: Annotated[
        bool,
        Option("--timeit", help="Print execution time"),
    ] = False

    pdb: Annotated[
        bool,
        Option("--pdb", help="Enter interp-level debugger in case of error"),
    ] = False

    spdb: Annotated[
        bool,
        Option("--spdb", help="Enter app-level debugger in case of error"),
    ] = False

    error_mode: Annotated[
        ErrorMode,
        Option(
            "-E",
            "--error-mode",
            help="Handling strategy for static errors",
            click_type=click.Choice(ErrorMode.__args__),
        ),
    ] = "eager"


@dataclass
class Filename_Optional_Args:
    """Filename is optional for the cleanup command only"""

    filename: Annotated[
        Optional[Path],
        Argument(help=""),
    ] = None


@dataclass
class Filename_Required_Args:
    filename: Annotated[
        Path,
        Argument(help=""),
    ]


@dataclass
class General_Args_With_Filename(Base_Args, Filename_Required_Args): ...
