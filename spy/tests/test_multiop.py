from spy.irgen.multiop import MultiOp
from spy.vm.builtins import B

def test_simple():
    myadd = MultiOp('myadd', 2)

    @myadd(B.w_i32, B.w_i32, w_restype=B.w_i32)
    def emit_add_i32() -> None:
        pass

    @myadd(B.w_str, B.w_str, w_restype=B.w_str)
    def emit_add_str() -> None:
        pass

    impl = myadd.lookup(B.w_i32, B.w_i32)
    assert impl is not None
    assert impl.w_restype == B.w_i32
    assert impl.emit is emit_add_i32

    impl = myadd.lookup(B.w_str, B.w_str)
    assert impl is not None
    assert impl.w_restype == B.w_str
    assert impl.emit is emit_add_str

    assert myadd.lookup(B.w_i32, B.w_str) is None
