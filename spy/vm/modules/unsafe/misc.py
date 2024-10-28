from spy.vm.b import B
from spy.vm.object import W_Type

def sizeof(w_T: W_Type) -> int:
    from .struct import W_StructType

    if w_T is B.w_i32:
        return 4
    elif w_T is B.w_f64:
        return 8
    elif isinstance(w_T, W_StructType):
        return w_T.size
    else:
        assert False
