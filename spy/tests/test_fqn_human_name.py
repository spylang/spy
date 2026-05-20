import pytest

from spy.fqn import FQN
from spy.vm.vm import SPyVM


@pytest.mark.usefixtures("init")
class TestFQNHumanName:
    @pytest.fixture
    def init(self):
        self.vm = SPyVM()
        # common aliases used across many tests
        self.vm.fqn_human_aliases[FQN("_list::list")] = FQN("list")
        self.vm.fqn_human_aliases[FQN("builtins::i32")] = FQN("i32")

    def test_no_alias(self):
        assert FQN("a::b").human_name(self.vm) == "a::b"

    def test_direct_alias(self):
        assert FQN("_list::list").human_name(self.vm) == "list"

    def test_prefix_match_with_qualifiers(self):
        # _list::list[i32] -> list[i32] via prefix match on _list::list
        assert FQN("_list::list[i32]").human_name(self.vm) == "list[i32]"

    def test_compositional(self):
        # qualifier builtins::i32 is also aliased to i32
        assert FQN("_list::list[builtins::i32]").human_name(self.vm) == "list[i32]"

    def test_inner_of_generic(self):
        self.vm.fqn_human_aliases[FQN("MyList[i32]::impl")] = FQN("MyList[i32]")
        assert FQN("MyList[i32]::impl").human_name(self.vm) == "MyList[i32]"

    def test_inner_of_generic_with_prefix(self):
        # _list::list[i32]::_ListImpl -> _list::list[i32] -> list[i32]
        self.vm.fqn_human_aliases[FQN("_list::list[i32]::_ListImpl")] = FQN(
            "_list::list[i32]"
        )
        assert FQN("_list::list[i32]::_ListImpl").human_name(self.vm) == "list[i32]"

    def test_nested_function_in_generic(self):
        # _list::list[i32]::_ListImpl::_push -> list[i32]::_push
        self.vm.fqn_human_aliases[FQN("_list::list[i32]::_ListImpl")] = FQN(
            "_list::list[i32]"
        )
        assert (
            FQN("_list::list[i32]::_ListImpl::_push").human_name(self.vm)
            == "list[i32]::_push"
        )

    def test_cycle_protection(self):
        self.vm.fqn_human_aliases[FQN("mod::A")] = FQN("mod::B")
        self.vm.fqn_human_aliases[FQN("mod::B")] = FQN("mod::A")
        result = FQN("mod::A").human_name(self.vm)
        assert isinstance(result, str)  # must terminate

    def test_bootstrap_builtins_alias(self):
        vm = SPyVM()
        assert vm.fqn_human_aliases[FQN("builtins::i32")] == FQN("i32")

    def test_bootstrap_list_alias(self):
        vm = SPyVM()
        assert vm.fqn_human_aliases[FQN("_list::list")] == FQN("list")

    def test_bootstrap_dict_alias(self):
        vm = SPyVM()
        assert vm.fqn_human_aliases[FQN("_dict::dict")] == FQN("dict")
