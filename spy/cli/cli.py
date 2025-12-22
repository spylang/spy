import sys
from typing import Any

from spy.cli.commands.build import build
from spy.cli.commands.cleanup import cleanup
from spy.cli.commands.colorize import colorize
from spy.cli.commands.execute import execute
from spy.cli.commands.imports import imports
from spy.cli.commands.parse import parse
from spy.cli.commands.pyparse import pyparse
from spy.cli.commands.redshift import redshift
from spy.cli.commands.symtable import symtable
from spy.cli.spy_typer import SpyGroupConfig, SpyTyper

app = SpyTyper(pretty_exceptions_enable=False, cls=SpyGroupConfig, no_args_is_help=True)

# Commands
# Each command should be written as an async function which takes
# a single dataclass as its only argument
# Aliases may be created by separating multiple names with , or |

# This is the order commands will appear in the --help

app.spy_command(execute, name="execute", default=True)
app.spy_command(build, name="build")
app.spy_command(redshift, name="redshift | rs")
app.spy_command(colorize, name="colorize")
app.spy_command(parse, name="parse")
app.spy_command(pyparse, name="pyparse")
app.spy_command(imports, name="imports")
app.spy_command(symtable, name="symtable")
app.spy_command(cleanup, name="cleanup")
