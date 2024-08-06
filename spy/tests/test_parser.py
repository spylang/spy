from typing import Any
import textwrap
import pytest
from spy import ast
from spy.parser import Parser
from spy.ast_dump import dump
from spy.util import print_diff
from spy.tests.support import CompilerTest, expect_errors, MatchAnnotation

@pytest.mark.usefixtures('init')
class TestParser:

    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir

    def parse(self, src: str) -> ast.Module:
        f = self.tmpdir.join('test.spy')
        src = textwrap.dedent(src)
        f.write(src)
        parser = Parser(src, str(f))
        self.mod = parser.parse()
        return self.mod

    def expect_errors(self, src: str, main: str, *anns: MatchAnnotation):
        with expect_errors(main, *anns):
            self.parse(src)

    def assert_dump(self, node: ast.Node, expected: str):
        dumped = dump(node, use_colors=False,
                      fields_to_ignore=('symtable',))
        dumped = dumped.strip()
        expected = textwrap.dedent(expected).strip()
        if '{tmpdir}' in expected:
            expected = expected.format(tmpdir=self.tmpdir)
        if dumped != expected:
            print_diff(expected, dumped, 'expected', 'got')
            pytest.fail("assert_dump failed")

    def test_Module(self):
        mod = self.parse("""
        def foo() -> void:
            pass
        """)
        expected = """
        Module(
            filename='{tmpdir}/test.spy',
            decls=[
                GlobalFuncDef(
                    funcdef=FuncDef(
                        color='red',
                        name='foo',
                        args=[],
                        return_type=Name(id='void'),
                        body=[
                            Pass(),
                        ],
                    ),
                ),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_FuncDef_arguments(self):
        mod = self.parse("""
        def foo(a: i32, b: float) -> void:
            pass
        """)
        expected = """
        Module(
            filename='{tmpdir}/test.spy',
            decls=[
                GlobalFuncDef(
                    funcdef=FuncDef(
                        color='red',
                        name='foo',
                        args=[
                            FuncArg(
                                name='a',
                                type=Name(id='i32'),
                            ),
                            FuncArg(
                                name='b',
                                type=Name(id='float'),
                            ),
                        ],
                        return_type=Name(id='void'),
                        body=[
                            Pass(),
                        ],
                    ),
                ),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_FuncDef_errors_1(self):
        src = """
        def foo():
            pass

        """
        self.expect_errors(
            src,
            "missing return type",
            ("", "def foo"),
        )

    def test_FuncDef_errors_2(self):
        src = """
        def foo(*args) -> void:
            pass
        """
        self.expect_errors(
            src,
            "*args is not supported yet",
            ("this is not supported", "args"),
        )

    def test_FuncDef_errors_3(self):
        src = """
        def foo(**kwargs) -> void:
            pass
        """
        self.expect_errors(
            src,
            "**kwargs is not supported yet",
            ("this is not supported", "kwargs"),
        )

    def test_FuncDef_errors_4(self):
        src = """
        def foo(a: i32 = 42) -> void:
            pass
        """
        self.expect_errors(
            src,
            "default arguments are not supported yet",
            ("this is not supported", "42"),
        )

    def test_FuncDef_errors_5(self):
        src = """
        def foo(a: i32, /, b: i32) -> void:
            pass
        """
        self.expect_errors(
            src,
            "positional-only arguments are not supported yet",
            ("this is not supported", "a: i32"),
        )

    def test_FuncDef_errors_6(self):
        src = """
        def foo(a: i32, *, b: i32) -> void:
            pass
        """
        self.expect_errors(
            src,
            "keyword-only arguments are not supported yet",
            ("this is not supported", "b: i32"),
        )

    def test_FuncDef_errors_7(self):
        src = """
        def foo(a, b) -> void:
            pass
        """
        self.expect_errors(
            src,
            "missing type for argument 'a'",
            ("type is missing here", "a"),
        )

    def test_FuncDef_errors_8(self):
        src = """
        @mydecorator
        def foo() -> void:
            pass
        """
        self.expect_errors(
            src,
            "decorators are not supported yet",
            ("this is not supported", "mydecorator"),
        )

    def test_FuncDef_body(self):
        mod = self.parse("""
        def foo() -> i32:
            return 42
        """)
        funcdef = mod.get_funcdef('foo')
        expected = """
        FuncDef(
            color='red',
            name='foo',
            args=[],
            return_type=Name(id='i32'),
            body=[
                Return(
                    value=Constant(value=42),
                ),
            ],
        )
        """
        self.assert_dump(funcdef, expected)

    def test_blue_FuncDef(self):
        mod = self.parse("""
        @blue
        def foo() -> i32:
            return 42
        """)
        funcdef = mod.get_funcdef('foo')
        expected = """
        FuncDef(
            color='blue',
            name='foo',
            args=[],
            return_type=Name(id='i32'),
            body=[
                Return(
                    value=Constant(value=42),
                ),
            ],
        )
        """
        self.assert_dump(funcdef, expected)

    def test_empty_return(self):
        mod = self.parse("""
        def foo() -> void:
            return
        """)
        stmt = mod.get_funcdef('foo').body[0]
        expected = """
        Return(
            value=Constant(value=None),
        )
        """
        self.assert_dump(stmt, expected)

    def test_unsupported_literal(self):
        # Eventually this test should be killed, when we support all the
        # literals
        src = """
        def foo() -> i32:
            return 42j
        """
        self.expect_errors(
            src,
            'unsupported literal: 42j',
            ('this is not supported yet', "42j"),
        )

    def test_GetItem(self):
        mod = self.parse("""
        def foo() -> void:
            return mylist[0]
        """)
        stmt = mod.get_funcdef('foo').body[0]
        expected = """
        Return(
            value=GetItem(
                value=Name(id='mylist'),
                index=Constant(value=0),
            ),
        )
        """
        self.assert_dump(stmt, expected)

    def test_SetItem(self):
        mod = self.parse("""
        def foo() -> void:
            mylist[0] = 42
        """)
        stmt = mod.get_funcdef('foo').body[0]
        expected = """
        SetItem(
            target=Name(id='mylist'),
            index=Constant(value=0),
            value=Constant(value=42),
        )
        """
        self.assert_dump(stmt, expected)

    def test_VarDef(self):
        mod = self.parse("""
        def foo() -> void:
            x: i32 = 42
        """)
        vardef, assign = mod.get_funcdef('foo').body[:2]
        vardef_expected = """
        VarDef(
            kind='var',
            name='x',
            type=Name(id='i32'),
        )
        """
        assign_expected = """
        Assign(
            target='x',
            value=Constant(value=42),
        )
        """
        self.assert_dump(vardef, vardef_expected)
        self.assert_dump(assign, assign_expected)

    def test_global_VarDef_const(self):
        mod = self.parse("""
        x: i32 = 42
        """)
        expected = f"""
        Module(
            filename='{self.tmpdir}/test.spy',
            decls=[
                GlobalVarDef(
                    vardef=VarDef(
                        kind='const',
                        name='x',
                        type=Name(id='i32'),
                    ),
                    assign=Assign(
                        target='x',
                        value=Constant(value=42),
                    ),
                ),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_global_VarDef_var(self):
        mod = self.parse("""
        var x: i32 = 42
        """)
        expected = f"""
        Module(
            filename='{self.tmpdir}/test.spy',
            decls=[
                GlobalVarDef(
                    vardef=VarDef(
                        kind='var',
                        name='x',
                        type=Name(id='i32'),
                    ),
                    assign=Assign(
                        target='x',
                        value=Constant(value=42),
                    ),
                ),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_global_VarDef_auto_const(self):
        mod = self.parse("""
        x = 42
        """)
        expected = f"""
        Module(
            filename='{self.tmpdir}/test.spy',
            decls=[
                GlobalVarDef(
                    vardef=VarDef(
                        kind='const',
                        name='x',
                        type=Auto(),
                    ),
                    assign=Assign(
                        target='x',
                        value=Constant(value=42),
                    ),
                ),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_global_VarDef_auto_var(self):
        mod = self.parse("""
        var x = 42
        """)
        expected = f"""
        Module(
            filename='{self.tmpdir}/test.spy',
            decls=[
                GlobalVarDef(
                    vardef=VarDef(
                        kind='var',
                        name='x',
                        type=Auto(),
                    ),
                    assign=Assign(
                        target='x',
                        value=Constant(value=42),
                    ),
                ),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_List(self):
        mod = self.parse("""
        def foo() -> void:
            return [1, 2, 3]
        """)
        stmt = mod.get_funcdef('foo').body[0]
        expected = """
        Return(
            value=List(
                items=[
                    Constant(value=1),
                    Constant(value=2),
                    Constant(value=3),
                ],
            ),
        )
        """
        self.assert_dump(stmt, expected)

    def test_Tuple(self):
        mod = self.parse("""
        def foo() -> void:
            return 1, 2, 3
        """)
        stmt = mod.get_funcdef('foo').body[0]
        expected = """
        Return(
            value=Tuple(
                items=[
                    Constant(value=1),
                    Constant(value=2),
                    Constant(value=3),
                ],
            ),
        )
        """
        self.assert_dump(stmt, expected)

    @pytest.mark.parametrize("op", "+ - * / // % ** << >> | ^ & @".split())
    def test_BinOp(self, op):
        # map the operator to the spy.ast class name
        binops = {
            '+':  'Add',
            '-':  'Sub',
            '*':  'Mul',
            '/':  'Div',
            '//': 'FloorDiv',
            '%':  'Mod',
            '**': 'Pow',
            '<<': 'LShift',
            '>>': 'RShift',
            '|':  'BitOr',
            '^':  'BitXor',
            '&':  'BitAnd',
            '@':  'MatMul',
        }
        OpClass = binops[op]
        #
        mod = self.parse(f"""
        def foo() -> i32:
            return x {op} 1
        """)
        stmt = mod.get_funcdef('foo').body[0]
        expected = f"""
        Return(
            value={OpClass}(
                left=Name(id='x'),
                right=Constant(value=1),
            ),
        )
        """
        self.assert_dump(stmt, expected)

    @pytest.mark.parametrize("op", "+ - ~ not".split())
    def test_UnaryOp(self, op):
        # map the operator to the spy.ast class name
        unops = {
            '+': 'UnaryPos',
            '-': 'UnaryNeg',
            '~': 'Invert',
            'not': 'Not',
        }
        OpClass = unops[op]
        #
        mod = self.parse(f"""
        def foo() -> i32:
            return {op} x
        """)
        stmt = mod.get_funcdef('foo').body[0]
        expected = f"""
        Return(
            value={OpClass}(
                value=Name(id='x'),
            ),
        )
        """
        self.assert_dump(stmt, expected)

    def test_negative_const(self):
        # special case -NUM, so that it's seen as a constant by the rest of the code
        mod = self.parse(f"""
        def foo() -> i32:
            return -123
        """)
        stmt = mod.get_funcdef('foo').body[0]
        expected = """
        Return(
            value=Constant(value=-123),
        )
        """
        self.assert_dump(stmt, expected)

    @pytest.mark.parametrize("op", "== != < <= > >= is is_not in not_in".split())
    def test_CompareOp(self, op):
        op = op.replace('_', ' ')  # is_not ==> is not
        # map the operator to the spy.ast class name
        cmpops = {
            '==':     'Eq',
            '!=':     'NotEq',
            '<':      'Lt',
            '<=':     'LtE',
            '>':      'Gt',
            '>=':     'GtE',
            'is':     'Is',
            'is not': 'IsNot',
            'in':     'In',
            'not in': 'NotIn',

        }
        OpClass = cmpops[op]
        #
        mod = self.parse(f"""
        def foo() -> i32:
            return x {op} 1
        """)
        stmt = mod.get_funcdef('foo').body[0]
        expected = f"""
        Return(
            value={OpClass}(
                left=Name(id='x'),
                right=Constant(value=1),
            ),
        )
        """
        self.assert_dump(stmt, expected)

    def test_CompareOp_chained(self):
        src = """
        def foo() -> i32:
            return 1 == 2 == 3
        """
        self.expect_errors(
            src,
            "not implemented yet: chained comparisons",
            ("this is not supported", "3"),
        )

    def test_Assign(self):
        mod = self.parse("""
        def foo() -> void:
            x = 42
        """)
        stmt = mod.get_funcdef('foo').body[0]
        expected = """
        Assign(
            target='x',
            value=Constant(value=42),
        )
        """
        self.assert_dump(stmt, expected)

    def test_Assign_unsupported_1(self):
        src = """
        def foo() -> void:
            a = b = 1
        """
        self.expect_errors(
            src,
            "not implemented yet: assign to multiple targets",
            ("this is not supported", "a = b = 1"),
        )

    def test_Assign_unsupported_2(self):
        src = """
        def foo() -> void:
            [a, b] = 1, 2
        """
        self.expect_errors(
            src,
            "not implemented yet: assign to complex expressions",
            ("this is not supported", "[a, b]"),
        )

    def test_UnpackAssign(self):
        mod = self.parse("""
        def foo() -> void:
            a, b, c = x
        """)
        stmt = mod.get_funcdef('foo').body[0]
        expected = """
        UnpackAssign(
            targets=[
                'a',
                'b',
                'c',
            ],
            value=Name(id='x'),
        )
        """
        self.assert_dump(stmt, expected)

    def test_Call(self):
        mod = self.parse("""
        def foo() -> i32:
            return bar(1, 2, 3)
        """)
        stmt = mod.get_funcdef('foo').body[0]
        expected = """
        Return(
            value=Call(
                func=Name(id='bar'),
                args=[
                    Constant(value=1),
                    Constant(value=2),
                    Constant(value=3),
                ],
            ),
        )
        """
        self.assert_dump(stmt, expected)

    def test_Call_errors(self):
        src = """
        def foo() -> i32:
            return Bar(1, 2, x=3)
        """
        self.expect_errors(
            src,
            "not implemented yet: keyword arguments",
            ("this is not supported", "x=3"),
        )

    def test_CallMethod(self):
        mod = self.parse("""
        def foo() -> i32:
            return a.b(1, 2)
        """)
        stmt = mod.get_funcdef('foo').body[0]
        expected = """
        Return(
            value=CallMethod(
                target=Name(id='a'),
                method='b',
                args=[
                    Constant(value=1),
                    Constant(value=2),
                ],
            ),
        )
        """
        self.assert_dump(stmt, expected)

    def test_If(self):
        mod = self.parse("""
        def foo() -> i32:
            if x:
                return 1
            else:
                return 2
        """)
        stmt = mod.get_funcdef('foo').body[0]
        expected = """
        If(
            test=Name(id='x'),
            then_body=[
                Return(
                    value=Constant(value=1),
                ),
            ],
            else_body=[
                Return(
                    value=Constant(value=2),
                ),
            ],
        )
        """
        self.assert_dump(stmt, expected)

    def test_StmtExpr(self):
        mod = self.parse("""
        def foo() -> void:
            42
        """)
        stmt = mod.get_funcdef('foo').body[0]
        expected = """
        StmtExpr(
            value=Constant(value=42),
        )
        """
        self.assert_dump(stmt, expected)

    def test_While(self):
        mod = self.parse("""
        def foo() -> void:
            while True:
                pass
        """)
        stmt = mod.get_funcdef('foo').body[0]
        expected = """
        While(
            test=Constant(value=True),
            body=[
                Pass(),
            ],
        )
        """
        self.assert_dump(stmt, expected)

    def test_from_import(self):
        mod = self.parse("""
        from testmod import a, b as b2
        """)
        #
        expected = """
        Module(
            filename='{tmpdir}/test.spy',
            decls=[
                Import(fqn=FQN('testmod::a'), asname='a'),
                Import(fqn=FQN('testmod::b'), asname='b2'),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_import(self):
        mod = self.parse("""
        import aaa
        import bbb as BBB
        import ccc, ddd as DDD
        """)
        #
        expected = """
        Module(
            filename='{tmpdir}/test.spy',
            decls=[
                Import(fqn=FQN('aaa::'), asname='aaa'),
                Import(fqn=FQN('bbb::'), asname='BBB'),
                Import(fqn=FQN('ccc::'), asname='ccc'),
                Import(fqn=FQN('ddd::'), asname='DDD'),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_walk(self):
        def isclass(x: Any, name: str) -> bool:
            return x.__class__.__name__ == name

        mod = self.parse("""
        def foo() -> void:
            if True:
                x = y + 1
        """)
        nodes: list[Any] = list(mod.walk())
        assert isclass(nodes[0], 'Module')
        assert isclass(nodes[1], 'GlobalFuncDef')
        assert isclass(nodes[2], 'FuncDef')
        assert isclass(nodes[3], 'Name') and nodes[3].id == 'void'
        assert isclass(nodes[4], 'If')
        assert isclass(nodes[5], 'Constant') and nodes[5].value is True
        assert isclass(nodes[6], 'Assign') and nodes[6].target == 'x'
        assert isclass(nodes[7], 'Add')
        assert isclass(nodes[8], 'Name') and nodes[8].id == 'y'
        assert isclass(nodes[9], 'Constant') and nodes[9].value == 1
        assert len(nodes) == 10
        #
        nodes2 = list(mod.walk(ast.Stmt))
        expected2 = [node for node in nodes if isinstance(node, ast.Stmt)]
        assert nodes2 == expected2
        #
        nodes3 = list(mod.walk(ast.Expr))
        expected3 = [node for node in nodes if isinstance(node, ast.Expr)]
        assert nodes3 == expected3

    def test_inner_FuncDef(self):
        mod = self.parse("""
        @blue
        def foo():
            def bar() -> void:
                pass
        """)
        expected = """
        Module(
            filename='{tmpdir}/test.spy',
            decls=[
                GlobalFuncDef(
                    funcdef=FuncDef(
                        color='blue',
                        name='foo',
                        args=[],
                        return_type=Name(id='dynamic'),
                        body=[
                            FuncDef(
                                color='red',
                                name='bar',
                                args=[],
                                return_type=Name(id='void'),
                                body=[
                                    Pass(),
                                ],
                            ),
                        ],
                    ),
                ),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_GetAttr(self):
        mod = self.parse("""
        def foo() -> void:
            a.b
        """)
        stmt = mod.get_funcdef('foo').body[0]
        expected = """
        StmtExpr(
            value=GetAttr(
                value=Name(id='a'),
                attr='b',
            ),
        )
        """
        self.assert_dump(stmt, expected)

    def test_SetAttr(self):
        mod = self.parse("""
        def foo() -> void:
            a.b = 42
        """)
        stmt = mod.get_funcdef('foo').body[0]
        expected = """
        SetAttr(
            target=Name(id='a'),
            attr='b',
            value=Constant(value=42),
        )
        """
        self.assert_dump(stmt, expected)
