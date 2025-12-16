from spy.analyze.importing import ImportAnalyzer
from spy.cli.base_args import (
    General_Args_With_Filename,
)
from spy.cli.support import init_vm


async def symtable(args: General_Args_With_Filename) -> None:
    """Dump the symtables"""
    modname = args.filename.stem
    vm = await init_vm(args)

    importer = ImportAnalyzer(vm, modname)
    importer.parse_all()
    scopes = importer.analyze_scopes(modname)
    scopes.pp()
