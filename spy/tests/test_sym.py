from spy.analyze.sym import FrameInfo, Scope, Symbol
from spy.location import Loc


def test_get_fresh_slot_no_double_suffix():
    # a src_name that already carries a `$NUM` suffix (a hidden temp like
    # `_$iter$0`) must not become `_$iter$0$0`: we probe from its base.
    # NOTE: get_fresh_slot is a pure query; the caller reserves the slot via
    # add(). Here we simulate that by poking _symbols directly.
    frameinfo = FrameInfo("test", "red", "function")
    assert frameinfo.get_fresh_slot("_$iter$0") == "_$iter$0"
    frameinfo._symbols["_$iter$0"] = None  # type: ignore[assignment]
    assert frameinfo.get_fresh_slot("_$iter$0") == "_$iter$1"
    frameinfo._symbols["_$iter$1"] = None  # type: ignore[assignment]
    assert frameinfo.get_fresh_slot("_$iter$0") == "_$iter$2"


def test_scope_clone():
    loc = Loc(filename="<test>", line_start=0, line_end=0, col_start=0, col_end=0)

    def make_sym(src_name: str, slot_name: str) -> Symbol:
        return Symbol(
            src_name,
            "var",
            "explicit",
            "direct",
            slot_name=slot_name,
            loc=loc,
            type_loc=loc,
            frame_depth=0,
        )

    frameinfo = FrameInfo("test", "red", "function")
    parent = Scope("foo", "red", "function", frameinfo=frameinfo, parent=None)
    block = Scope("if.then", "red", "block", frameinfo=frameinfo, parent=parent)
    x0 = make_sym("x", "x$0")
    y0 = make_sym("y", "y$0")
    block.add(x0)
    block.add(y0)

    x1 = make_sym("x", "x$1")
    new_parent = Scope("foo2", "red", "function", frameinfo=frameinfo, parent=None)
    clone = block.clone(new_parent, {x0: x1})

    assert clone is not block
    assert (clone.name, clone.color, clone.kind) == ("if.then", "red", "block")
    assert clone.frameinfo is frameinfo
    assert clone.parent is new_parent
    # only the symbols in `rename` are replaced, and the original is untouched
    assert clone.symbols == {"x": x1, "y": y0}
    assert block.symbols == {"x": x0, "y": y0}
    # clones do not show up in the tree of scopes
    assert new_parent.children == []
    assert parent.children == [block]
