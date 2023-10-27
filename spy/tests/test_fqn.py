import pytest
from spy.fqn import FQN

def test_init_fullname():
    a = FQN("a.b.c::xxx")
    assert a.fullname == "a.b.c::xxx"
    assert a.modname == "a.b.c"
    assert a.attr == "xxx"

def test_init_parts():
    a = FQN(modname="a.b.c", attr="xxx")
    assert a.fullname == "a.b.c::xxx"
    assert a.modname == "a.b.c"
    assert a.attr == "xxx"

def test_wrong_init():
    with pytest.raises(AssertionError):
        FQN("aaa")
    with pytest.raises(AssertionError):
        FQN("aaa::bbb::ccc")
    with pytest.raises(AssertionError):
        FQN("aaa::bbb", modname="aaa")
    with pytest.raises(AssertionError):
        FQN("aaa::bbb", attr="bbb")
    with pytest.raises(AssertionError):
        FQN()
    with pytest.raises(AssertionError):
        FQN(modname="aaa")

def test_str_repr():
    fqn = FQN("aaa::bbb")
    assert repr(fqn) == "FQN('aaa::bbb')"
    assert str(fqn) == 'aaa::bbb'

def test_hash_eq():
    a = FQN("aaa::bbb")
    b = FQN("aaa::bbb")
    assert a == b
    assert hash(a) == hash(b)

def test_c_name():
    a = FQN("a.b.c::xxx")
    assert a.c_name == "a_b_c_xxx"
