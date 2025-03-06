import pytest
from spy.fqn_parser import FQN, NSPart, tokenize

def test_tokenizer():
    assert tokenize("foo") == ["foo"]
    assert tokenize("mod::foo") == ["mod", "::", "foo"]
    assert tokenize("a.b.c::") == ["a.b.c", "::"]
    assert tokenize("list[i32]") == ["list", "[", "i32", "]"]

def test_single_unqualified_part():
    fqn = FQN("foo")
    assert len(fqn.parts) == 1
    assert fqn.parts[0].name == "foo"
    assert fqn.parts[0].qualifiers == []
    assert fqn.parts[0].suffix == 0

def test_two_parts():
    fqn = FQN("mod::foo")
    assert len(fqn.parts) == 2
    assert fqn.parts[0].name == "mod"
    assert fqn.parts[0].qualifiers == []
    assert fqn.parts[1].name == "foo"
    assert fqn.parts[1].qualifiers == []

def test_dot_in_name():
    fqn = FQN("a.b.c::foo")
    assert len(fqn.parts) == 2
    assert fqn.parts[0].name == "a.b.c"
    assert fqn.parts[0].qualifiers == []
    assert fqn.parts[1].name == "foo"
    assert fqn.parts[1].qualifiers == []

def test_single_part_with_qualifier():
    fqn = FQN("list[i32]")
    assert len(fqn.parts) == 1
    assert fqn.parts[0].name == "list"
    assert len(fqn.parts[0].qualifiers) == 1
    assert fqn.parts[0].qualifiers[0].parts[0].name == "i32"

def test_nested_qualifiers():
    fqn = FQN("dict[str, unsafe::ptr[i32]]")
    assert len(fqn.parts) == 1
    assert fqn.parts[0].name == "dict"
    assert len(fqn.parts[0].qualifiers) == 2
    assert fqn.parts[0].qualifiers[0].parts[0].name == "str"
    assert fqn.parts[0].qualifiers[1].parts[0].name == "unsafe"
    assert fqn.parts[0].qualifiers[1].parts[1].name == "ptr"
    assert fqn.parts[0].qualifiers[1].parts[1].qualifiers[0].parts[0].name == "i32"

def test_suffix():
    fqn = FQN("mod::foo[i32]#1")
    assert fqn.parts[0].name == "mod"
    assert fqn.parts[1].name == "foo"
    assert fqn.parts[1].qualifiers[0].parts[0].name == "i32"
    assert fqn.parts[1].suffix == 1
    assert str(fqn) == "mod::foo[i32]#1"
