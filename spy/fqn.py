from typing import Optional, Any

class FQN:
    """
    Fully qualified name.

    A FQN uniquely identify a named object inside the current VM. It is
    formated as 'modname::attr', where 'modname' can be composed of multiple
    parts separated by dots (e.g. 'a.b.c').

    In some cases we might want to generate two FQN with the same
    'modname::attr' part, but we still want them to be unique. In those cases,
    we attach an uniq_suffix to them, and the FQN is formatted as
    'modname::attr#suffix', e.g. 'test::foo#42'.

    This hapens for example with closures:

    @blue
    def make_fn(T):
        def fn(x: T) -> T:
            return ...
        return fn

    fn_i32 = make_fn(i32)  # fqn is 'test::foo#1'
    fn_f64 = make_fn(f64)  # fqn is 'test::foo#2'

    See also SPyVM.get_unique_FQN().
    """
    modname: str
    attr: str
    uniq_suffix: str

    def __init__(self,
                 fullname: Optional[str] = None,
                 *,
                 modname: Optional[str] = None,
                 attr: Optional[str] = None,
                 uniq_suffix: str = '',
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
        self.uniq_suffix = uniq_suffix

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

    def is_module(self) -> bool:
        return self.attr == ""

    def is_object(self) -> bool:
        return self.attr != ""

    @property
    def fullname(self) -> str:
        fn = f'{self.modname}::{self.attr}'
        if self.uniq_suffix != '':
            fn += '#' + self.uniq_suffix
        return fn

    @property
    def c_name(self) -> str:
        modname = self.modname.replace('.', '_')
        cn = f'spy_{modname}__{self.attr}'
        if self.uniq_suffix != '':
            cn += '__' + self.uniq_suffix
        return cn

    @property
    def spy_name(self) -> str:
        return f'{self.modname}.{self.attr}'
