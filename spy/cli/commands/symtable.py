from spy.analyze.importing import ImportAnalyzer
from spy.cli._runners import init_vm
from spy.cli.commands.base_args import Base_Args_With_Filename


async def symtable(args: Base_Args_With_Filename) -> None:
    """Dump the symtables"""
    modname = args.filename.stem
    vm = await init_vm(args)

    importer = ImportAnalyzer(vm, modname)
    importer.parse_all()
    scopes = importer.analyze_scopes(modname)
    scopes.pp()
