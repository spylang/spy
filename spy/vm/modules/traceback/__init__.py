from typing import TYPE_CHECKING

from spy.vm.registry import ModuleRegistry

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM

TRACEBACK = ModuleRegistry("traceback")

from . import tb  # noqa: F401 -- side effects
