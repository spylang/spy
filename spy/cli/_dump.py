from spy.backend.spy import FQN_FORMAT, SPyBackend
from spy.vm.function import W_ASTFunc
from spy.vm.vm import SPyVM


def dump_spy_mod(vm: SPyVM, modname: str, full_fqn: bool) -> None:
    fqn_format: FQN_FORMAT = "full" if full_fqn else "short"
    b = SPyBackend(vm, fqn_format=fqn_format)
    print(b.dump_mod(modname))


def dump_spy_mod_ast(vm: SPyVM, modname: str) -> None:
    for fqn, w_obj in vm.fqns_by_modname(modname):
        if isinstance(w_obj, W_ASTFunc) and w_obj.color == "red" and w_obj.fqn == fqn:
            print(f"`{fqn}` = ", end="")
            w_obj.funcdef.pp()
            print()
