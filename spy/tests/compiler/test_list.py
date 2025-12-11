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

    def test_literal(self):
        mod = self.compile("""
        def foo() -> list[i32]:
            x = [1, 2, 3]
            return x
        """)
        x = mod.foo()
        assert x == [1, 2, 3]
