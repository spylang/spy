"""
SPy `types` module.
"""

from spy.vm.module import W_Module
from spy.vm.registry import ModuleRegistry

TYPES = ModuleRegistry('types', '<types>')

TYPES.add('module', W_Module._w)
