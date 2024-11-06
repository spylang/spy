import pytest
from spy.fqn_parser import QN, NSPart, tokenize

def test_tokenizer():
    assert tokenize("foo") == ["foo"]
    assert tokenize("mod::foo") == ["mod", "::", "foo"]
    assert tokenize("a.b.c::") == ["a.b.c", "::"]
    assert tokenize("list[i32]") == ["list", "[", "i32", "]"]

def test_single_unqualified_part():
    qn = QN.parse("foo")
    assert len(qn.parts) == 1
    assert qn.parts[0].name == "foo"
    assert qn.parts[0].qualifiers == []

def test_two_parts():
    qn = QN.parse("mod::foo")
    assert len(qn.parts) == 2
    assert qn.parts[0].name == "mod"
    assert qn.parts[0].qualifiers == []
    assert qn.parts[1].name == "foo"
    assert qn.parts[1].qualifiers == []

def test_dot_in_name():
    qn = QN.parse("a.b.c::foo")
    assert len(qn.parts) == 2
    assert qn.parts[0].name == "a.b.c"
    assert qn.parts[0].qualifiers == []
    assert qn.parts[1].name == "foo"
    assert qn.parts[1].qualifiers == []

def test_single_part_with_qualifier():
    qn = QN.parse("list[i32]")
    assert len(qn.parts) == 1
    assert qn.parts[0].name == "list"
    assert len(qn.parts[0].qualifiers) == 1
    assert qn.parts[0].qualifiers[0].parts[0].name == "i32"

def test_nested_qualifiers():
    qn = QN.parse("dict[str, unsafe::ptr[i32]]")
    assert len(qn.parts) == 1
    assert qn.parts[0].name == "dict"
    assert len(qn.parts[0].qualifiers) == 2
    assert qn.parts[0].qualifiers[0].parts[0].name == "str"
    assert qn.parts[0].qualifiers[1].parts[0].name == "unsafe"
    assert qn.parts[0].qualifiers[1].parts[1].name == "ptr"
    assert qn.parts[0].qualifiers[1].parts[1].qualifiers[0].parts[0].name == "i32"
