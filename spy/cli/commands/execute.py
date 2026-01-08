from dataclasses import dataclass

from spy.analyze.importing import ImportAnalyzer
from spy.cli._runners import execute_spy_main, init_vm
from spy.cli.commands.shared_args import (
    Base_Args,
    Filename_Required_Args,
    _execute_options,
)


@dataclass
class Execute_Args(Base_Args, _execute_options, Filename_Required_Args): ...


async def execute(args: Execute_Args) -> None:
    """Execute the file in the vm (default)"""
    modname = args.filename.stem
    vm = await init_vm(args)

    importer = ImportAnalyzer(vm, modname)
    importer.parse_all()
    importer.import_all()
    w_mod = vm.modules_w[modname]

    execute_spy_main(vm, w_mod, redshift=False, _timeit=args.timeit)
