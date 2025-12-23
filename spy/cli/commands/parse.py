from dataclasses import dataclass

from spy.analyze.importing import ImportAnalyzer
from spy.cli._runners import init_vm
from spy.cli.commands.shared_args import (
    Base_Args,
    Filename_Required_Args,
)


@dataclass
class Parse_Args(Base_Args, Filename_Required_Args): ...


async def parse(args: Parse_Args) -> None:
    """Dump the SPy AST"""
    modname = args.filename.stem
    vm = await init_vm(args)

    importer = ImportAnalyzer(vm, modname)
    importer.parse_all()

    orig_mod = importer.getmod(modname)
    orig_mod.pp()
