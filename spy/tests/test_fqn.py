import pytest
from spy.fqn import NSPart, QN, FQN

def test_QN_init_fullname():
    a = QN("a.b.c::xxx")
    assert a.fullname == "a.b.c::xxx"
    assert a.modname == "a.b.c"
    assert a.parts == [
        NSPart("a.b.c", []),
        NSPart("xxx", [])
    ]

def test_QN_init_parts():
    a = QN(['a.b.c', 'xxx'])
    assert a.fullname == "a.b.c::xxx"
    assert a.modname == "a.b.c"

def test_many_QNs():
    assert str(QN("aaa")) == "aaa"
    assert str(QN("aaa::bbb::ccc")) == "aaa::bbb::ccc"

def test_QN_str_repr():
    a = QN("aaa::bbb")
    assert repr(a) == "QN('aaa::bbb')"
    assert str(a) == 'aaa::bbb'

def test_QN_hash_eq():
    a = QN("aaa::bbb")
    b = QN("aaa::bbb")
    assert a == b
    assert hash(a) == hash(b)

def test_qualifiers():
    a = QN("a::b[x, y]::c")
    assert a.fullname == "a::b[x, y]::c"
    assert a.modname == "a"
    assert a.parts == [
        NSPart("a", []),
        NSPart("b", [NSPart("x", []), NSPart("y", [])]),
        NSPart("c", [])
    ]

def test_nested_qualifiers():
    a = QN("foo::list[Ptr[Point]]")
    assert a.fullname == "foo::list[Ptr[Point]]"

def test_QN_nested():
    a = QN("aaa::bbb")
    b = a.nested("ccc")
    assert b.fullname == "aaa::bbb::ccc"

def test_FQN():
    a = FQN.make("aaa::bbb", suffix="0")
    assert a.fullname == "aaa::bbb#0"

def test_FQN_str():
    a = FQN.make("aaa::bbb", suffix='0')
    assert str(a) == "aaa::bbb#0"
    assert a.c_name == "spy_aaa$bbb$0"
    b = FQN.make("aaa::bbb", suffix='')
    assert str(b) == "aaa::bbb"
    assert b.c_name == "spy_aaa$bbb"

def test_FQN_hash_eq():
    a = FQN.make("aaa::bbb", suffix="0")
    b = FQN.make("aaa::bbb", suffix="0")
    assert a == b
    assert hash(a) == hash(b)

def test_FQN_c_name_dotted():
    a = FQN.make("a.b.c::xxx", suffix="0")
    assert a.c_name == "spy_a_b_c$xxx$0"

def test_FQN_parse():
    fqn = FQN.parse("aaa::bbb")
    assert fqn.qn == QN("aaa::bbb")
    assert fqn.suffix == ""
    #
    fqn = FQN.parse("aaa::bbb#0")
    assert fqn.qn == QN("aaa::bbb")
    assert fqn.suffix == "0"

def test_qualifiers_c_name():
    a = FQN.make("a::b[x, y]::c", suffix="0")
    assert a.c_name == "spy_a$b__x_y$c$0"

def test_nested_qualifiers_c_name():
    a = FQN.make("a::list[Ptr[x, y]]::c", suffix="0")
    assert a.c_name == "spy_a$list__Ptr__x_y$c$0"
