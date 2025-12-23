from spy.cli.commands.shared_args import Base_Args_With_Filename
from spy.magic_py_parse import magic_py_parse


async def pyparse(args: Base_Args_With_Filename) -> None:
    """Dump the Python AST"""
    with open(args.filename) as f:
        src = f.read()
    mod = magic_py_parse(src)
    mod.pp()
