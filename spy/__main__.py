from typing import Annotated
from pathlib import Path
import typer
#
from spy.errors import SPyCompileError
from spy.parser import Parser
from spy.irgen.typechecker import TypeChecker
from spy.irgen.modgen import ModuleGen
from spy.vm.vm import SPyVM
from spy.vm.module import W_Module
from spy.vm.function import W_Function

app = typer.Typer(pretty_exceptions_enable=False)
OPT = typer.Option

@app.command()
def main(filename: Path,
         parse: Annotated[bool, OPT(help="dump the AST and exit")] = False,
         ) -> None:
    vm = SPyVM()
    p = Parser.from_filename(str(filename))
    try:
        mod = p.parse()
        if parse == 'parse':
            mod.pp()
            return
        t = TypeChecker(vm, mod)
        t.check_everything()
        modgen = ModuleGen(vm, t, mod)
        w_mod = modgen.make_w_mod()
        print_w_mod(w_mod)
    except SPyCompileError as e:
        print(e.format(use_colors=True))

def print_w_mod(w_mod: W_Module) -> None:
    print(f'Module {w_mod.name}:')
    for attr, w_obj in w_mod.content.values_w.items():
        print(f'    {attr}: {w_obj}')

    print()
    for attr, w_obj in w_mod.content.values_w.items():
        if isinstance(w_obj, W_Function):
            w_obj.w_code.pp()

if __name__ == '__main__':
    app()
