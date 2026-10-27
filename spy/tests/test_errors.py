import pickle

from spy.errors import SPyError


def test_SPyError_pickle_roundtrip():
    err = SPyError("W_NameError", "hello")
    err2 = pickle.loads(pickle.dumps(err))
    assert err2.etype == "W_NameError"
    assert err2.w_exc.message == "hello"
