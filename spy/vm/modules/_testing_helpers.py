from typing import TYPE_CHECKING

from spy.errors import SPyError
from spy.vm.builtin import builtin_method
from spy.vm.object import W_Object
from spy.vm.registry import ModuleRegistry

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

TH = _TESTING_HELPERS = ModuleRegistry("_testing_helpers")


@TH.builtin_func
def w_raise_no_loc(vm: "SPyVM") -> None:
    "Raise a SPyError without specifying any loc"
    raise SPyError("W_ValueError", "this is some error")


@TH.builtin_type("SomeType")
class W_SomeType(W_Object):
    """
    An arbitrary type used by tests.

    Known tests using it:
      - test_if_while_assert_cond_type_mismatch (no implicit conversion to bool)
    """

    @builtin_method("__new__")
    @staticmethod
    def w_new(vm: "SPyVM") -> "W_SomeType":
        return W_SomeType()
