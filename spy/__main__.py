from typing import Annotated
from pathlib import Path
import typer
#
from spy.errors import SPyCompileError
from spy.parser import Parser
from spy.irgen.typechecker import TypeChecker
from spy.irgen.modgen import ModuleGen
from spy.vm.vm import SPyVM

app = typer.Typer()

@app.command()
def parse(filename: Path):
    main(filename, 'parse')

@app.command()
def irgen(filename: str):
    main(filename, 'irgen')

def main(filename: Path, command: str) -> None:
    vm = SPyVM()
    p = Parser.from_filename(filename)
    try:
        mod = p.parse()
        if command == 'parse':
            mod.pp()
            return
        elif command == 'irgen':
            t = TypeChecker(vm, mod)
            t.check_everything()
            modgen = ModuleGen(vm, t, mod)
            w_mod = modgen.make_w_mod()
            print_w_mod(w_mod)
            return
        else:
            assert False
    except SPyCompileError as e:
        print(e.format(use_colors=True))

def print_w_mod(self, w_mod):
    print(f'Module {w_mod.name}:')
    for attr, w_obj in w_mod.content.values_w.items():
        print(f'    {attr}: {w_obj}')

if __name__ == '__main__':
    app()
