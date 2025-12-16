import asyncio
import pdb as stdlib_pdb  # to distinguish from the "--pdb" option  # to distinguish from the "--pdb" option
import re
import sys
import traceback
from functools import wraps
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Iterable,
    Optional,
    Protocol,
    Sequence,
)

import click
import typer
from typer.core import DEFAULT_MARKUP_MODE, MarkupMode, TyperGroup

from spy.backend.spy import FQN_FORMAT, SPyBackend
from spy.cli.base_args import (
    Base_Args,
)
from spy.doppler import ErrorMode
from spy.errors import SPyError
from spy.textbuilder import Color
from spy.vendored.dataclass_typer import dataclass_typer
from spy.vm.debugger.spdb import SPdb
from spy.vm.function import W_ASTFunc
from spy.vm.vm import SPyVM

GLOBAL_VM: Optional[SPyVM] = None


class TyperDefaultCommand(typer.core.TyperCommand):
    """Type that indicates if a command is the default command."""


class AppGroupConfig(TyperGroup):
    def __init__(
        self,
        *,
        name: str | None = None,
        commands: dict[str, click.Command] | Sequence[click.Command] | None = None,
        rich_markup_mode: MarkupMode = DEFAULT_MARKUP_MODE,
        rich_help_panel: str | None = None,
        **attrs: Any,
    ) -> None:
        """
        The __init__ and make_context commands are shadowed to permit using a default command if none is given.
        See https://github.com/fastapi/typer/issues/18
        """
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
            for name, command in reversed(self.commands.items()):
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
            )  # Hardcoded assumption that the default command takes something that looks like a filename. This is necessary to distinguish misformed subcommands from misformed file names
        ):
            args = [self.default_command] + args

        return super().make_context(info_name, args, parent, **extra)

    # Command Aliases
    # To alias a command, include the aliases in the command name,
    # separated by commas or a |
    # From https://github.com/fastapi/typer/issues/132

    _CMD_SPLIT_P = re.compile(r" *[,|] *")

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        cmd_name = self._group_cmd_name(self.commands.values(), cmd_name)
        result = super().get_command(ctx, cmd_name)
        return result

    def _group_cmd_name(
        self, group_command_names: Iterable[click.Command], default_name: str
    ) -> str:
        for cmd in group_command_names:
            if cmd.name and default_name in self._CMD_SPLIT_P.split(cmd.name):
                return cmd.name
        return default_name


class SpyTyper(typer.Typer):
    def __init__(self, *args, **kwargs):
        kwargs["add_completion"] = False
        super().__init__(*args, **kwargs)

    def _command_with_default_option(self: typer.Typer, default=False, *args, **kwargs):
        """
        More chicanery to allow typer to provide a diffault option
        """
        if default:
            kwargs["cls"] = TyperDefaultCommand
        s: typer.Typer = super()  # type:ignore
        return s.command(*args, **kwargs)

    def spy_command(self, user_func: Any, *cmd_args, **cmd_kwargs) -> Callable:  # type: ignore
        """
        Decorator to turn an async function into a SPy subcommand
        The async function should take a single dataclass as an argument
        Arguments to the spy_command decorator are passed to typer.app.command, i.e. "name"
        """

        def syncify(f: Callable[["Base_Args"], Any]) -> Callable[["Base_Args"], Any]:
            @wraps(f)
            def inner(args: "Base_Args") -> Any:
                if sys.platform == "emscripten":
                    return asyncio.create_task(_pyodide_main(f, args))
                else:
                    return asyncio.run(_run_user_func_and_catch_spy_errors(f, args))

            return inner

        self._command_with_default_option(*cmd_args, **cmd_kwargs)(
            dataclass_typer(syncify(user_func))
        )


async def _pyodide_main(user_func: Callable, args: "Base_Args") -> None:
    """
    For some reasons, it seems that pyodide doesn't print exceptions
    uncaught exceptions which escapes an asyncio task. This is a small wrapper
    to ensure that we display a proper traceback in that case
    """
    try:
        await _run_user_func_and_catch_spy_errors(user_func, args)
    except BaseException:
        traceback.print_exc()


async def _run_user_func_and_catch_spy_errors(
    user_func: Callable, args: "Base_Args"
) -> None:
    """
    A wrapper around the user provided command,
    to catch/display SPy errors and to implement --pdb
    """
    try:
        return await user_func(args)
    except SPyError as e:
        ## traceback.print_exc()
        ## print()

        # special case SPdbQuit
        if e.etype == "W_SPdbQuit":
            print("SPdbQuit")
            sys.exit(1)

        print(e.format(use_colors=True))

        if args.spdb:
            # post-mortem applevel debugger
            assert GLOBAL_VM is not None
            w_tb = e.w_exc.w_tb
            assert w_tb is not None
            spdb = SPdb(GLOBAL_VM, w_tb)
            spdb.post_mortem()
        elif args.pdb:
            # post-mortem interp-level debugger
            info = sys.exc_info()
            stdlib_pdb.post_mortem(info[2])
        sys.exit(1)
    except Exception as e:
        if not args.pdb:
            raise
        traceback.print_exc()
        info = sys.exc_info()
        stdlib_pdb.post_mortem(info[2])
        sys.exit(1)


class Init_Args(Protocol):
    error_mode: ErrorMode
    filename: Path


async def init_vm(args: Init_Args) -> SPyVM:
    global GLOBAL_VM

    if args.filename.suffix == ".py":
        print(
            f"Error: {args.filename} is a .py file, not a .spy file.", file=sys.stderr
        )
        sys.exit(1)

    srcdir = args.filename.parent
    vm = await SPyVM.async_new()

    GLOBAL_VM = vm

    vm.robust_import_caching = True  # don't raise if .spyc are unreadable/invalid

    vm.path.append(str(srcdir))
    if args.error_mode == "warn":
        args.error_mode = "lazy"

        def emit_warning(err: SPyError) -> None:
            print(Color.set("yellow", "[warning] "), end="")
            print(err.format())

        vm.emit_warning = emit_warning
    return vm


def dump_spy_mod(vm: SPyVM, modname: str, full_fqn: bool) -> None:
    fqn_format: FQN_FORMAT = "full" if full_fqn else "short"
    b = SPyBackend(vm, fqn_format=fqn_format)
    print(b.dump_mod(modname))


def dump_spy_mod_ast(vm: SPyVM, modname: str) -> None:
    for fqn, w_obj in vm.fqns_by_modname(modname):
        if isinstance(w_obj, W_ASTFunc) and w_obj.color == "red" and w_obj.fqn == fqn:
            print(f"`{fqn}` = ", end="")
            w_obj.funcdef.pp()
            print()
