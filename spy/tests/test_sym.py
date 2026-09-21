from spy.analyze.sym import FrameInfo


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
