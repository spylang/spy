from spy.analyze.importing import ImportAnalyzer
from spy.cli._runners import init_vm
from spy.cli.commands.shared_args import Base_Args_With_Filename


async def imports(args: Base_Args_With_Filename) -> None:
    """Dump the (recursive) list of imports"""
    modname = args.filename.stem
    vm = await init_vm(args)

    importer = ImportAnalyzer(vm, modname)
    importer.parse_all()
    importer.pp()
