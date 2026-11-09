"""
PROTOTYPE tests: `str` (and the `_str` stdlib module) can be passed through the
boundary between the interpreter and the prebuilt compiled code, because a `str`
is already a pointer to a spy_StrObject in the linear memory of the VM.
"""

import pytest

from spy.build.native_stdlib import get_native_stdlib
from spy.fqn import FQN
from spy.vm.function import W_Func
from spy.vm.native import W_NativeFunc
from spy.vm.vm import SPyVM

SRC = """
def s_upper(s: str) -> str:
    return s.upper()

def s_find(s: str, t: str) -> i32:
    return s.find(t)

def s_count(s: str, t: str) -> i32:
    return s.count(t)

def s_replace(s: str, a: str, b: str) -> str:
    return s.replace(a, b)

def s_add(a: str, b: str) -> str:
    return a + b

def s_lt(a: str, b: str) -> bool:
    return a < b

def s_isspace(s: str) -> bool:
    return s.isspace()

def s_strip(s: str) -> str:
    return s.strip()
"""


def make_vm(tmpdir, native: bool) -> SPyVM:
    vm = SPyVM(native_stdlib=get_native_stdlib(("_str",)) if native else False)
    tmpdir.join("strtest.spy").write(SRC)
    vm.path.append(str(tmpdir))
    vm.import_("strtest")
    return vm


def call(vm: SPyVM, name: str, *args):
    w_func = vm.lookup_global(FQN(f"strtest::{name}"))
    assert isinstance(w_func, W_Func)
    return vm.unwrap(vm.fast_call(w_func, [vm.wrap(a) for a in args]))


class TestNativeStr:
    @pytest.fixture(scope="class")
    def vms(self, tmpdir_factory):
        tmpdir = tmpdir_factory.mktemp("native_str")
        return make_vm(tmpdir, native=False), make_vm(tmpdir, native=True)

    def test_methods_are_replaced(self, vms):
        _, vn = vms
        # `_str` is imported lazily, by the first use of a str method
        call(vn, "s_upper", "x")
        for name in ("upper", "replace", "__add__", "__lt__", "isspace"):
            w_func = vn.lookup_global(FQN(f"_str::methods::{name}"))
            assert isinstance(w_func, W_NativeFunc), name

    @pytest.mark.parametrize(
        "name, args",
        [
            ("s_upper", ("héllo wörld ß",)),
            ("s_upper", ("",)),
            ("s_find", ("abc def abc", "def")),
            ("s_find", ("abc", "zzz")),
            ("s_count", ("abababab", "ab")),
            ("s_replace", ("a-b-c-d", "-", "+")),
            ("s_replace", ("aaaa", "aa", "b")),
            ("s_add", ("foo", "bär")),
            ("s_lt", ("abc", "abd")),
            ("s_lt", ("b", "a")),
            ("s_isspace", ("  \t",)),
            ("s_isspace", ("a ",)),
            ("s_strip", ("  hi there \n",)),
        ],
    )
    def test_same_result_as_interp(self, vms, name, args):
        vi, vn = vms
        assert call(vn, name, *args) == call(vi, name, *args)

    def test_result_is_a_usable_str(self, vms):
        # the str returned by compiled code is a normal sealed W_Str, which
        # can be given back to interpreted and compiled functions
        _, vn = vms
        s = call(vn, "s_add", "foo", "bar")
        assert s == "foobar"
        assert call(vn, "s_upper", s) == "FOOBAR"
