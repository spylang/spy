import sys
import time
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
from spy.cli.support import init_vm
from spy.vm.b import B
from spy.vm.function import W_ASTFunc, W_FuncType
from spy.vm.module import W_Module
from spy.vm.vm import SPyVM


@dataclass
class _execute_mixin:
    redshift: Annotated[
        bool,
        Option("-s", "--redshift", help="Redshift the module before executing"),
    ] = False


@dataclass
class Execute_Args(Base_Args, _execute_mixin, Filename_Required_Args): ...


async def execute(args: Execute_Args) -> None:
    """Execute the file in the vm"""  # TODO make this the default operation when no command is given
    modname = args.filename.stem
    vm = await init_vm(args)

    importer = ImportAnalyzer(vm, modname)
    importer.parse_all()
    importer.import_all()
    w_mod = vm.modules_w[modname]

    # If we're not redshifting, execute and return immediately
    if not args.redshift:
        execute_spy_main(args, vm, w_mod)
        return

    # Redshift the code here
    vm.redshift(error_mode=args.error_mode)

    execute_spy_main(args, vm, w_mod)


def execute_spy_main(args: Execute_Args, vm: SPyVM, w_mod: W_Module) -> None:
    w_main_functype = W_FuncType.parse("def() -> None")
    w_main = w_mod.getattr_maybe("main")
    if w_main is None:
        print("Cannot find function main()")
        return

    vm.typecheck(w_main, w_main_functype)
    assert isinstance(w_main, W_ASTFunc)

    # find the redshifted version, if necessary
    if args.redshift:
        assert not w_main.is_valid
        assert w_main.w_redshifted_into is not None
        w_main = w_main.w_redshifted_into
        assert w_main.redshifted
    else:
        assert not w_main.redshifted

    a = time.time()
    w_res = vm.fast_call(w_main, [])
    b = time.time()
    if args.timeit:
        print(f"main(): {b - a:.3f} seconds", file=sys.stderr)
    assert w_res is B.w_None
