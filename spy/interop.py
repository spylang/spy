"""
Utility functions to make it easier to use SPy as a frontend for other
compilers.
"""

import sys
from pathlib import Path
from spy.vm.vm import SPyVM
from spy.vm.module import W_Module

def redshift(filename: str|Path) -> tuple[SPyVM, W_Module]:
    """
    Perform redshift on the given file
    """
    filename = Path(filename)
    modname = filename.stem
    builddir = filename.parent
    vm = SPyVM()
    vm.path.append(str(builddir))
    w_mod = vm.import_(modname)
    vm.redshift(lazy_errors=False)
    return vm, w_mod


def main(argv: list[str]) -> None:
    """
    Example of how to use spy.interop.redshift
    """
    from spy.vm.function import W_ASTFunc
    filename = argv[1]
    vm, w_mod = redshift(filename)
    for fqn, w_obj in w_mod.items_w():
        print(fqn, w_obj)
        if isinstance(w_obj, W_ASTFunc):
            print('functype:', w_obj.w_functype)
            print('locals:')
            assert w_obj.locals_types_w is not None
            for varname, w_type in w_obj.locals_types_w.items():
                print('   ', varname, w_type)
            print('AST:')
            w_obj.funcdef.pp()
            print()




if __name__ == '__main__':
    main(sys.argv)
