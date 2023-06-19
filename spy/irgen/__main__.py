import sys
from spy.errors import SPyCompileError
from spy.parser import Parser
from spy.irgen.module import ModuleGen
from spy.vm.vm import SPyVM

def main() -> None:
    vm = SPyVM()
    p = Parser.from_filename(sys.argv[1])
    try:
        mod = p.parse()
        modgen = ModuleGen(vm, mod)
        w_mod = modgen.make_w_mod()
    except SPyCompileError as e:
        print(e)
    else:
        print(f'Module {w_mod.name}:')
        for attr, w_obj in w_mod.content.values_w.items():
            print(f'    {attr}: {w_obj}')

if __name__ == '__main__':
    main()