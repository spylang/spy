import py

from spy.analyze.importing import ImportAnalyzer
from spy.cli._runners import init_vm
from spy.cli.commands.shared_args import Base_Args_With_Filename


async def symtable(args: Base_Args_With_Filename) -> None:
    """Dump the symtables"""
    filename = py.path.local(args.filename)
    modname = args.filename.stem
    vm = await init_vm(args)

    importer = ImportAnalyzer(vm, modname, use_spyc=not args.no_spyc)

    parsed_mod = importer.parse_one(filename)
    scopes = importer.analyze_one(modname, parsed_mod)
    scopes.pp()
