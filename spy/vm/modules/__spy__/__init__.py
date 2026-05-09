"""
SPy `__spy__` module.
"""

from spy.vm.registry import ModuleRegistry

SPY = ModuleRegistry("__spy__")

from . import (
    interp_dict,  # noqa: F401 -- side effects
    interp_list,  # noqa: F401 -- side effects
    interp_tuple,  # noqa: F401 -- side effects
    misc,  # noqa: F401 -- side effects
)
