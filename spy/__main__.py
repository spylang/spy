from typing import Annotated, Any, no_type_check
from pathlib import Path
import typer
import py.path
from spy.errors import SPyCompileError
from spy.compiler import CompilerPipeline
from spy.vm.vm import SPyVM

app = typer.Typer(pretty_exceptions_enable=False)

def boolopt(help: str) -> Any:
    return Annotated[bool, typer.Option(help=help)]

def do_pyparse(filename: str) -> None:
    import ast as py_ast
    with open(filename) as f:
        src = f.read()
    mod = py_ast.parse(src)
    mod.pp()

@no_type_check
@app.command()
def main(filename: Path,
         pyparse: boolopt("dump the Python AST exit") = False,
         parse: boolopt("dump the SPy AST and exit") = False,
         dis: boolopt("disassemble the SPy IR and exit") = False,
         cwrite: boolopt("create the .c file and exit") = False,
         ) -> None:
    filename = py.path.local(filename)
    builddir = filename.dirpath()
    vm = SPyVM()
    compiler = CompilerPipeline(vm, filename, builddir)

    try:
        if pyparse:
            do_pyparse(str(filename))
        elif parse:
            mod = compiler.parse()
            mod.pp()
        elif dis:
            w_mod = compiler.irgen()
            w_mod.pp()
        elif cwrite:
            compiler.cwrite()
        else:
            compiler.cbuild()

    except SPyCompileError as e:
        print(e.format(use_colors=True))

if __name__ == '__main__':
    app()
