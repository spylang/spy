from dataclasses import dataclass
from typing import Annotated

from typer import Option

from spy.analyze.importing import ImportAnalyzer
from spy.cli._format import dump_spy_mod, dump_spy_mod_ast
from spy.cli._runners import execute_spy_main, init_vm
from spy.cli.commands.shared_args import (
    Base_Args,
    Filename_Required_Args,
    _execute_flag,
    _execute_options,
)


@dataclass
class _redshift_mixin:
    full_fqn: Annotated[
        bool,
        Option("--full-fqn", help="Show full FQNs in redshifted modules"),
    ] = False

    human_readable: Annotated[
        bool,
        Option("--human-readable", help="Show full FQNs in redshifted modules"),
    ] = False


@dataclass
class Redshift_Args(
    Base_Args, _redshift_mixin, _execute_flag, _execute_options, Filename_Required_Args
): ...


async def redshift(args: Redshift_Args) -> None:
    """
    Perform redshift and dump or execute the module
    """

    modname = args.filename.stem
    vm = await init_vm(args)

    importer = ImportAnalyzer(vm, modname)
    importer.parse_all()
    importer.import_all()

    vm.ast_color_map = {}
    vm.redshift(error_mode=args.error_mode)

    if args.execute:
        w_mod = vm.modules_w[modname]
        execute_spy_main(vm, w_mod, redshift=True, _timeit=args.timeit)
    else:
        if args.human_readable:
            dump_spy_mod(vm, modname, args.full_fqn)
        else:  # not args.human_readable
            dump_spy_mod_ast(vm, modname)
