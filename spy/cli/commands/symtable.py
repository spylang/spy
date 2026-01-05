from spy.analyze.importing import ImportAnalyzer
from spy.cli._runners import init_vm
from spy.cli.commands.shared_args import Base_Args_With_Filename


async def symtable(args: Base_Args_With_Filename) -> None:
    """Dump the symtables"""
    modname = args.filename.stem
    vm = await init_vm(args)

    importer = ImportAnalyzer(vm, modname, use_spyc=not args.no_spyc)
    importer.parse_all()

    orig_mod = importer.getmod(modname)
    scopes = importer.analyze_one(modname, orig_mod)
    scopes.pp()
