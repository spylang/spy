import pytest

from spy.vm.b import B
from spy.vm.modules.unsafe.misc import sizeof


@pytest.mark.parametrize(
    "w_T, expected",
    [
        (B.w_i8, 1),
        (B.w_u8, 1),
        (B.w_i32, 4),
        (B.w_u32, 4),
        (B.w_f32, 4),
        (B.w_f64, 8),
    ],
)
def test_sizeof_primitives(w_T, expected):
    assert sizeof(w_T) == expected
