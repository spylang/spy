"""
First half of the `builtins` module.

This contains the definition of the BUILTINS registry, and registers the
"basic" builtins, i.e., all the primitive types and constants which are used
everywhere.

Additionally, it also contains an alias B, because it's shorter to type than
BUILTINS

The rest of the builtins are registered in vm/modules/builtins.py, which is
the proper place where to put modules.

This strange setup is needed to avoid circular imports, since B.* is needed
all over the place and we need to import it very early.
"""

from spy.vm.registry import ModuleRegistry
from spy.vm.object import (W_Object, W_Type, w_DynamicType)

BUILTINS = ModuleRegistry('builtins')
B = BUILTINS

B.add('object', W_Object._w)
B.add('type', W_Type._w)
B.add('dynamic', w_DynamicType)
