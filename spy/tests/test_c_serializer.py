import pytest

from spy.backend.c.serializer import C_PRESERVE_NAMING, check_c_preserve


def test_check_c_preserve():
    for naming in C_PRESERVE_NAMING:
        assert check_c_preserve(naming) == f"${naming}"


def test_check_non_c_preserve():
    namings = (
        "dEfault",  # C is case-sensitive, so only `default` is reserved
        "myName",
        "__name_s",
    )
    for naming in namings:
        assert check_c_preserve(naming) == f"{naming}"
