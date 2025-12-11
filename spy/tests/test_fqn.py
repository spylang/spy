from spy.fqn import FQN, NSPart


def test_FQN_init_fullname():
    a = FQN("a.b.c::xxx")
    assert a.fullname == "a.b.c::xxx"
    assert a.modname == "a.b.c"
    assert a.parts == (NSPart("a.b.c", ()), NSPart("xxx", ()))


def test_FQN_init_parts():
    a = FQN(["a.b.c", "xxx"])
    assert a.fullname == "a.b.c::xxx"
    assert a.modname == "a.b.c"


def test_FQN_suffix():
    a = FQN("aaa::bbb#1")
    assert a.fullname == "aaa::bbb#1"
    assert a.parts[-1].suffix == "1"


def test_many_FQNs():
    assert str(FQN("aaa")) == "aaa"
    assert str(FQN("aaa::bbb::ccc")) == "aaa::bbb::ccc"


def test_FQN_str_repr():
    a = FQN("aaa::bbb")
    assert repr(a) == "FQN('aaa::bbb')"
    assert str(a) == "aaa::bbb"


def test_FQN_hash_eq():
    a = FQN("aaa::bbb")
    b = FQN("aaa::bbb")
    assert a == b
    assert hash(a) == hash(b)
    a0 = FQN("aaa::bbb#0")
    b0 = FQN("aaa::bbb#0")
    assert a0 == b0
    assert hash(a0) == hash(b0)


def test_qualifiers():
    a = FQN("a::b[x, y]::c")
    assert a.fullname == "a::b[x, y]::c"
    assert a.modname == "a"
    assert a.parts == (
        NSPart("a", ()),
        NSPart("b", (FQN("x"), FQN("y"))),
        NSPart("c", ()),
    )


def test_nested_qualifiers():
    a = FQN("mod::dict[str, unsafe::ptr[mymod::Point]]")
    assert a.fullname == "mod::dict[str, unsafe::ptr[mymod::Point]]"


def test_FQN_join():
    a = FQN("a")
    b = a.join("b")
    assert b.fullname == "a::b"
    c = b.join("c", ["i32"])
    assert c.fullname == "a::b::c[i32]"
    d = a.join("d", [FQN("mod::x")])
    assert d.fullname == "a::d[mod::x]"
    e = a.join("e", ["mod::y"])
    assert e.fullname == "a::e[mod::y]"


def test_FQN_str():
    a = FQN("aaa::bbb#1")  # Use a non-zero suffix
    assert str(a) == "aaa::bbb#1"
    assert a.c_name == "spy_aaa$bbb$1"
    b = FQN("aaa::bbb")
    assert str(b) == "aaa::bbb"
    assert b.c_name == "spy_aaa$bbb"


def test_FQN_c_name_dotted():
    a = FQN("a.b.c::xxx#1")  # Use a non-zero suffix
    assert a.c_name == "spy_a_b_c$xxx$1"


def test_qualifiers_c_name():
    a = FQN("a::b[x, y]::c#2")  # Use a non-zero suffix
    assert a.c_name == "spy_a$b__x_y$c$2"


def test_nested_qualifiers_c_name():
    a = FQN("a::list[Ptr[x, y]]::c#3")  # Use a non-zero suffix
    assert a.c_name == "spy_a$list__Ptr__x_y$c$3"


def test_FQN_human_name():
    # see also tests/vm/test_function.py::test_FunctionType_fqn
    assert FQN("a::b").human_name == "a::b"
    assert FQN("builtins::i32").human_name == "i32"
    func = FQN("builtins").join(
        "def", ["builtins::i32", "builtins::f64", "builtins::str"]
    )
    assert func.human_name == "def(i32, f64) -> str"


def test_FQN_with_qualifiers():
    a = FQN("mod::list")
    b = a.with_qualifiers(["i32"])
    assert b.fullname == "mod::list[i32]"
    # Verify original FQN is not modified
    assert a.fullname == "mod::list"

    # Test adding qualifiers to an FQN that already has qualifiers
    c = FQN("mod::dict[str]")
    d = c.with_qualifiers(["i32"])
    assert d.fullname == "mod::dict[str, i32]"
    # Verify original FQN is not modified
    assert c.fullname == "mod::dict[str]"

    # Test with FQN objects as qualifiers
    e = FQN("mod::map")
    f = e.with_qualifiers([FQN("mod::key"), FQN("mod::value")])
    assert f.fullname == "mod::map[mod::key, mod::value]"
    # Verify original FQN is not modified
    assert e.fullname == "mod::map"


def test_FQN_match():
    a = FQN("mod::ptr[i32]::load")
    assert a.match("mod::ptr[i32]::load")
    assert a.match("mod::ptr[*]::load")
    assert a.match("mod::ptr[i32]::*")
    assert a.match("mod::ptr[*]::*")
    #
    assert not a.match("mod::ptr[i32]::store")
    assert not a.match("mod::ptr[*]::store")
    assert not a.match("load")


def test_FQN_with_suffix():
    a = FQN("a::b")
    a1 = a.with_suffix("1")
    assert a.fullname == "a::b"
    assert a1.fullname == "a::b#1"


def test_FQN_parent():
    fqn = FQN("a::b::c")
    assert fqn.parent() == FQN("a::b")
