from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import click
from typer import Argument, Option

from spy.doppler import ErrorMode


@dataclass
class Base_Args:
    """These arguments can be applied to any spy command/subcommand"""

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
class Filename_Required_Args:
    filename: Annotated[
        Path,
        Argument(help=""),
    ]
    # Since this argument doesn't have a default value, it must come last
    # in the list of base classes of dataclasses that inherit from it


@dataclass
class Base_Args_With_Filename(Base_Args, Filename_Required_Args): ...
