from typing import TYPE_CHECKING
from spy.vm.b import B
from spy.vm.object import W_Object, W_Void, W_Dynamic
from spy.vm.str import W_Str
from spy.vm.module import W_Module
from . import OP
if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
