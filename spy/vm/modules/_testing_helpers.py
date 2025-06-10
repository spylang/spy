from typing import TYPE_CHECKING, Annotated
from spy.fqn import FQN
from spy.errors import SPyError
from spy.vm.b import B
from spy.vm.builtin import builtin_func
from spy.vm.registry import ModuleRegistry

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

TH = _TESTING_HELPERS = ModuleRegistry('_testing_helpers')


@TH.builtin_func
def w_raise_no_loc(vm: 'SPyVM') -> None:
    "Raise a SPyError without specifying any loc"
    raise SPyError('W_ValueError', 'this is some error')
