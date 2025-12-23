import asyncio
import re
import sys
from functools import wraps
from typing import (
    Any,
    Callable,
    Iterable,
    Sequence,
)

import click
import typer
from typer.core import DEFAULT_MARKUP_MODE, MarkupMode, TyperGroup
from typer.models import CommandFunctionType

from spy.cli._runners import _pyodide_main, _run_command
from spy.cli.commands.shared_args import Base_Args
from spy.vendored.dataclass_typer import dataclass_typer


class TyperDefaultCommand(typer.core.TyperCommand):
    """Type that indicates if a command is the default command."""


class SpyGroupConfig(TyperGroup):
    """
    Configuration class with some methods overridden to provide custom behavior

    The __init__ and make_context commands are shadowed to permit using a default command if no subcommand is given.
    See https://github.com/fastapi/typer/issues/18

    See below for implementation of command aliases
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        commands: dict[str, click.Command] | Sequence[click.Command] | None = None,
        rich_markup_mode: MarkupMode = DEFAULT_MARKUP_MODE,
        rich_help_panel: str | None = None,
        **attrs: Any,
    ) -> None:
        super().__init__(
            name=name,
            commands=commands,
            rich_markup_mode=rich_markup_mode,
            rich_help_panel=rich_help_panel,
            **attrs,
        )
        # find the default command if any
        self.default_command = None
        if len(self.commands) > 1:
            for name, command in reversed(list(self.commands.items())):
                if isinstance(command, TyperDefaultCommand):
                    self.default_command = name
                    break

    def make_context(
        self,
        info_name: str | None,
        args: list[str],
        parent: click.Context | None = None,
        **extra: Any,
    ) -> click.Context:
        # if --help is specified, show the group help
        # else if default command was specified in the group and no args or no subcommand is specified, use the default command

        all_command_aliases = [
            part for cmd in self.commands for part in self._CMD_SPLIT_P.split(cmd)
        ]

        if (
            self.default_command
            and (not args or args[0] not in all_command_aliases)
            and "--help" not in args
            and any(
                (".spy" in arg or ".py" in arg) for arg in args
            )  # Hardcoded assumption that the default command takes something that looks like a filename.
            # This is necessary to distinguish misformed subcommands from file names, i.e.
            # `spy example.spy`` should run but `spy execuuute` should fail with a 'no such command' error
        ):
            args = [self.default_command] + args

        return super().make_context(info_name, args, parent, **extra)

    # Allow Command Aliases
    # To alias a command, include the aliases in the command name,
    # separated by commas or a |
    # From https://github.com/fastapi/typer/issues/132

    _CMD_SPLIT_P = re.compile(r" *[,|] *")

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        """
        Given a command or alias, get the 'real' name (e.g. 'x | run | execute') and
        look it up in the command list
        """
        cmd_name = self._group_cmd_name(self.commands.values(), cmd_name)
        result = super().get_command(ctx, cmd_name)
        return result

    def _group_cmd_name(
        self, group_command_names: Iterable[click.Command], lookup_name: str
    ) -> str:
        """Given a name (or alias) look up the name of the command it belongs to"""
        for cmd in group_command_names:
            if cmd.name and lookup_name in self._CMD_SPLIT_P.split(cmd.name):
                return cmd.name
        return lookup_name


class SpyTyper(typer.Typer):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["add_completion"] = (
            False  # Hide the default --install-completion and --show-completion options for cleanliness
        )
        super().__init__(*args, **kwargs)

    def _command_with_default_option(
        self: typer.Typer, default: bool = False, *args: Any, **kwargs: Any
    ) -> Callable[[CommandFunctionType], CommandFunctionType]:
        """
        Allow spy_command() to take a "default" argument, which marks
        a single subcommand to be selected if none is provided
        """
        if default:
            kwargs["cls"] = TyperDefaultCommand
        return super().command(*args, **kwargs)  # type: ignore

    def spy_command(self, user_func: Any, /, *cmd_args, **cmd_kwargs) -> Callable:  # type: ignore
        """
        Turns async function into a SPy subcommand
        The async function should take a single dataclass as an argument
        Args and Kwargs are passed to typer.app.command, i.e. "name"
        """

        def syncify(f: Callable[["Base_Args"], Any]) -> Callable[["Base_Args"], Any]:
            @wraps(f)
            def inner(args: "Base_Args") -> Any:
                if sys.platform == "emscripten":
                    return asyncio.create_task(_pyodide_main(f, args))
                else:
                    return asyncio.run(_run_command(f, args))

            return inner

        self._command_with_default_option(*cmd_args, **cmd_kwargs)(
            dataclass_typer(syncify(user_func))
        )
