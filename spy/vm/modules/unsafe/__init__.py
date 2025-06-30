from typing import TYPE_CHECKING
import fixedint
from spy.vm.primitive import W_I32
from spy.vm.b import B
from spy.vm.builtin import builtin_type
from spy.vm.w import W_Object, W_Type
from spy.vm.registry import ModuleRegistry
from spy.vm.opimpl import W_OpImpl, W_OpArg
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

# XXX: ideally, we want to limit the number of modules which can use unsafe
# features. E.g., we could say that they need to end in .unsafe.spy or
# something like that. But for now, it's just a normal module.
UNSAFE = ModuleRegistry('unsafe')

from . import ptr     # noqa: F401 -- side effects
from . import mem     # noqa: F401 -- side effects
