import linecache
import sys
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from spy.doppler import DopplerFrame
from spy.fqn import FQN
from spy.location import Loc
from spy.textbuilder import TextBuilder
from spy.vm.astframe import ASTFrame
from spy.vm.builtin import builtin_method
from spy.vm.classframe import ClassFrame
from spy.vm.modframe import ModFrame
from spy.vm.object import W_Object

from . import TRACEBACK

if TYPE_CHECKING:
    from spy.vm.vm import SPyVM
