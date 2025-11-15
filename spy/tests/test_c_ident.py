import pytest

from spy.backend.c import c_ast as C


def test_check_c_preserve():
    for naming in C.Ident.C_PRESERVE_NAMING:
        assert str(C.Ident(naming)) == f"{naming}$"


def test_check_non_c_preserve():
    namings = (
        "dEfault",  # C is case-sensitive, so only `default` is reserved
        "myName",
        "__name_s",
    )
    for naming in namings:
        assert str(C.Ident(naming)) == f"{naming}"
