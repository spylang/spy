"""
(Fully) Qualified Names in SPy.

A Qualified Name (QN) identifies a function or a class inside a namespace.

A Fully Qualified Name (FQN) identifies an *unique* named object inside the
current VM.

The difference between QNs and FQNs becomes apparent for example with
closures:

@blue
def make_fn(T):
    def fn(x: T) -> T:
        # QN is 'test::fn'
        return ...
    return fn

fn_i32 = make_fn(i32)  # QN is 'test::fn', FQN is 'test::fn#1'
fn_f64 = make_fn(f64)  # QN is 'test::fn', FQN is 'test::fn#2'

Note that the QN is a property of the object, while the FQN basically
identifies a global symbol.

QN are formated as 'modname::attr', where 'modname' can be composed of
multiple parts separated by dots (e.g. 'a.b.c').

FQNs are formatted as 'modname::attr#suffix'.

See also SPyVM.get_unique_FQN().
"""

from typing import Optional, Any

class QN:
    modname: str
    attr: str

    def __init__(self,
                 fullname: Optional[str] = None,
                 *,
                 modname: Optional[str] = None,
                 attr: Optional[str] = None,
                 ) -> None:
        if fullname is None:
            assert modname is not None
            assert attr is not None
        else:
            assert modname is None
            assert attr is None
            assert fullname.count('::') == 1
            modname, attr = fullname.split('::')
        #
        self.modname = modname
        self.attr = attr

    def __repr__(self) -> str:
        return f"QN({self.fullname!r})"

    def __str__(self) -> str:
        return self.fullname

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, QN):
            return NotImplemented
        return self.fullname == other.fullname

    def __hash__(self) -> int:
        return hash(self.fullname)

    @property
    def fullname(self) -> str:
        return f'{self.modname}::{self.attr}'


class FQN:
    modname: str
    attr: str
    suffix: str

    def __init__(self, *args, **kwargs):
        raise ValueError("You cannot instantiate an FQN directly. "
                         "Please use vm.get_FQN()")

    @classmethod
    def make(cls, modname: str, attr: str, suffix: str) -> 'FQN':
        obj = cls.__new__(cls)
        obj.modname = modname
        obj.attr = attr
        obj.suffix = suffix
        return obj

    @classmethod
    def make_global(cls, modname: str, attr: str) -> 'FQN':
        """
        Return the FQN corresponding to a global name.

        Until we have generics, global names are supposed to be unique, so we
        can just use suffix=""
        """
        return cls.make(modname, attr, suffix="")

    @property
    def fullname(self) -> str:
        s = f'{self.modname}::{self.attr}'
        if self.suffix != '':
            s += '#' + self.suffix
        return s

    def __repr__(self) -> str:
        return f"FQN({self.fullname!r})"

    def __str__(self) -> str:
        return self.fullname

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, FQN):
            return NotImplemented
        return self.fullname == other.fullname

    def __hash__(self) -> int:
        return hash(self.fullname)

    @property
    def c_name(self) -> str:
        modname = self.modname.replace('.', '_')
        cn = f'spy_{modname}__{self.attr}'
        if self.suffix != '':
            cn += '__' + self.suffix
        return cn

    @property
    def spy_name(self) -> str:
        return f'{self.modname}.{self.attr}'

    def is_module(self) -> bool:
        return self.attr == ""

    def is_object(self) -> bool:
        return self.attr != ""
