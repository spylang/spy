import pytest
from spy.fqn import QN, FQN

def test_QN_init_fullname():
    a = QN("a.b.c::xxx")
    assert a.fullname == "a.b.c::xxx"
    assert a.modname == "a.b.c"
    assert a.attr == "xxx"

def test_QN_init_parts():
    a = QN(modname="a.b.c", attr="xxx")
    assert a.fullname == "a.b.c::xxx"
    assert a.modname == "a.b.c"
    assert a.attr == "xxx"

def test_QN_wrong_init():
    with pytest.raises(AssertionError):
        QN("aaa")
    with pytest.raises(AssertionError):
        QN("aaa::bbb::ccc")
    with pytest.raises(AssertionError):
        QN("aaa::bbb", modname="aaa")
    with pytest.raises(AssertionError):
        QN("aaa::bbb", attr="bbb")
    with pytest.raises(AssertionError):
        QN()
    with pytest.raises(AssertionError):
        QN(modname="aaa")

def test_QN_str_repr():
    a = QN("aaa::bbb")
    assert repr(a) == "QN('aaa::bbb')"
    assert str(a) == 'aaa::bbb'

def test_QN_hash_eq():
    a = QN("aaa::bbb")
    b = QN("aaa::bbb")
    assert a == b
    assert hash(a) == hash(b)

def test_FQN():
    a = FQN.make("aaa", "bbb", suffix="0")
    assert a.modname == "aaa"
    assert a.attr == "bbb"
    assert a.suffix == "0"
    assert a.fullname == "aaa::bbb#0"

def test_FQN_str():
    a = FQN.make("aaa", "bbb", suffix='0')
    assert str(a) == "aaa::bbb#0"
    assert a.c_name == "spy_aaa__bbb__0"
    b = FQN.make("aaa", "bbb", suffix='')
    assert str(b) == "aaa::bbb"
    assert b.c_name == "spy_aaa__bbb"

def test_FQN_hash_eq():
    a = FQN.make("aaa", "bbb", suffix="0")
    b = FQN.make("aaa", "bbb", suffix="0")
    assert a == b
    assert hash(a) == hash(b)

def test_FQN_c_name_dotted():
    a = FQN.make("a.b.c", "xxx", suffix="0")
    assert a.c_name == "spy_a_b_c__xxx__0"

def test_FQN_parse():
    fqn = FQN.parse("aaa::bbb")
    assert fqn.modname == "aaa"
    assert fqn.attr == "bbb"
    assert fqn.suffix == ""
    #
    fqn = FQN.parse("aaa::bbb#0")
    assert fqn.modname == "aaa"
    assert fqn.attr == "bbb"
    assert fqn.suffix == "0"
