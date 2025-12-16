from dataclasses import dataclass
from typing import (
    Annotated,
)

from typer import Option

from spy.analyze.importing import ImportAnalyzer
from spy.cli.base_args import (
    Base_Args,
    Filename_Required_Args,
)
from spy.cli.support import dump_spy_mod, dump_spy_mod_ast, init_vm
from spy.vm.function import W_ASTFunc
from spy.vm.vm import SPyVM


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
class Redshift_Args(Base_Args, _redshift_mixin, Filename_Required_Args): ...


async def redshift(args: Redshift_Args) -> None:
    """
    Perform redshift and dump the result
    """

    modname = args.filename.stem
    vm = await init_vm(args)

    importer = ImportAnalyzer(vm, modname)
    importer.parse_all()
    importer.import_all()

    vm.ast_color_map = {}
    vm.redshift(error_mode=args.error_mode)

    if args.human_readable:
        dump_spy_mod(vm, modname, args.full_fqn)
    else:  # not args.human_readable
        dump_spy_mod_ast(vm, modname)
