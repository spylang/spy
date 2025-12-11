from spy.fqn import FQN
from spy.tests.support import CompilerTest, only_interp


class TestList(CompilerTest):
    @only_interp
    def test_list_type(self):
        # check that by using the builtin 'list', we actually get
        # 'stdlib/_list.spy::list'
        src = """
        def foo() -> type:
            return list[i32]
        """
        mod = self.compile(src)
        w_T = mod.foo(unwrap=False)
        assert w_T.fqn == FQN("_list::list[i32]::_ListImpl")
        assert w_T.is_struct(self.vm)
