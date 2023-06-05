import pytest
from spy.util import MagicExtend

def test_MagicExtend():
    extend = MagicExtend('MyModule')

    class MyModule:
        @extend.register
        class A:
            pass

    @extend
    class A:
        x = 42

    assert A is MyModule.A
    assert A.x == 42

    with pytest.raises(AttributeError, match='class B is not registered as extendable'):
        @extend
        class B:
            pass
