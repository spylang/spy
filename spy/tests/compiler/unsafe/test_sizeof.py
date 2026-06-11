from spy.vm.b import B
from spy.vm.modules.unsafe.misc import sizeof


def test_sizeof_primitives():
    assert sizeof(B.w_bool) == 1
    assert sizeof(B.w_i8) == 1
    assert sizeof(B.w_u8) == 1
    assert sizeof(B.w_i32) == 4
    assert sizeof(B.w_u32) == 4
    assert sizeof(B.w_f32) == 4
    assert sizeof(B.w_f64) == 8
