"""
First half of the `builtins` module.

This contains the empty definition of the BUILTINS registry. Additionally, it
also contains an alias B, because it's shorter to type than BUILTINS

Many of the fundamental types are registered using @B.builtin_type and @B.add
inside vm/object.py, vm/primitive.py, etc.

The rest of the builtins are registered in vm/modules/builtins.py, which is
the proper place where to put modules.

This strange setup is needed to avoid circular imports, since B.* is needed
all over the place and we need to import it very early.

Morever, it also contains the empty definition of the OPERATOR module, since
we also need it very early.
"""

from spy.vm.registry import ModuleRegistry

BUILTINS: ModuleRegistry = ModuleRegistry('builtins')
B: ModuleRegistry = BUILTINS

OPERATOR: ModuleRegistry = ModuleRegistry('operator')
OP: ModuleRegistry = OPERATOR
