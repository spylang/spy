import textwrap
from typing import Any

import pytest

from spy import ast
from spy.ast_dump import dump
from spy.parser import Parser
from spy.tests.support import MatchAnnotation, expect_errors
from spy.util import print_diff


@pytest.mark.usefixtures("init")
class TestParser:
    @pytest.fixture
    def init(self, tmpdir):
        self.tmpdir = tmpdir

    def parse(self, src: str) -> ast.Module:
        f = self.tmpdir.join("test.spy")
        src = textwrap.dedent(src)
        f.write(src)
        parser = Parser(src, str(f))
        self.mod = parser.parse()
        return self.mod

    def expect_errors(self, src: str, main: str, *anns: MatchAnnotation):
        with expect_errors(main, *anns):
            self.parse(src)

    def assert_dump(self, node: ast.Node, expected: str):
        dumped = dump(node, use_colors=False, fields_to_ignore=("symtable",))
        dumped = dumped.strip()
        expected = textwrap.dedent(expected).strip()
        if "{tmpdir}" in expected:
            expected = expected.format(tmpdir=self.tmpdir)
        if dumped != expected:
            print_diff(expected, dumped, "expected", "got")
            pytest.fail("assert_dump failed")

    def test_Module(self):
        mod = self.parse(
            """
        def foo() -> None:
            pass
        """
        )
        expected = """
        Module(
            filename='{tmpdir}/test.spy',
            docstring=None,
            decls=[
                GlobalFuncDef(
                    funcdef=FuncDef(
                        color='red',
                        kind='plain',
                        name='foo',
                        args=[],
                        vararg=None,
                        return_type=Constant(value=None),
                        docstring=None,
                        body=[
                            Pass(),
                        ],
                        decorators=[],
                    ),
                ),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_FuncDef_arguments(self):
        mod = self.parse(
            """
        def foo(a: i32, b: float) -> None:
            pass
        """
        )
        expected = """
        Module(
            filename='{tmpdir}/test.spy',
            docstring=None,
            decls=[
                GlobalFuncDef(
                    funcdef=FuncDef(
                        color='red',
                        kind='plain',
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
                        vararg=None,
                        return_type=Constant(value=None),
                        docstring=None,
                        body=[
                            Pass(),
                        ],
                        decorators=[],
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

    def test_FuncDef_errors_3(self):
        src = """
        def foo(**kwargs) -> None:
            pass
        """
        self.expect_errors(
            src,
            "**kwargs is not supported yet",
            ("this is not supported", "kwargs"),
        )

    def test_FuncDef_errors_4(self):
        src = """
        def foo(a: i32 = 42) -> None:
            pass
        """
        self.expect_errors(
            src,
            "default arguments are not supported yet",
            ("this is not supported", "42"),
        )

    def test_FuncDef_errors_5(self):
        src = """
        def foo(a: i32, /, b: i32) -> None:
            pass
        """
        self.expect_errors(
            src,
            "positional-only arguments are not supported yet",
            ("this is not supported", "a: i32"),
        )

    def test_FuncDef_errors_6(self):
        src = """
        def foo(a: i32, *, b: i32) -> None:
            pass
        """
        self.expect_errors(
            src,
            "keyword-only arguments are not supported yet",
            ("this is not supported", "b: i32"),
        )

    def test_FuncDef_errors_7(self):
        src = """
        def foo(a, b) -> None:
            pass
        """
        self.expect_errors(
            src,
            "missing type for argument 'a'",
            ("type is missing here", "a"),
        )

    def test_FuncDef_decorator(self):
        mod = self.parse(
            """
        @mydecorator
        def foo() -> None:
            pass
        """
        )
        funcdef = mod.get_funcdef("foo")
        expected = """
        FuncDef(
            color='red',
            kind='plain',
            name='foo',
            args=[],
            vararg=None,
            return_type=Constant(value=None),
            docstring=None,
            body=[
                Pass(),
            ],
            decorators=[
                Name(id='mydecorator'),
            ],
        )
        """
        self.assert_dump(funcdef, expected)

    def test_FuncDef_multiple_decorators(self):
        mod = self.parse(
            """
        @deco1
        @deco2.attr
        @deco3(arg)
        def foo() -> None:
            pass
        """
        )
        funcdef = mod.get_funcdef("foo")
        expected = """
        FuncDef(
            color='red',
            kind='plain',
            name='foo',
            args=[],
            vararg=None,
            return_type=Constant(value=None),
            docstring=None,
            body=[
                Pass(),
            ],
            decorators=[
                Name(id='deco1'),
                GetAttr(
                    value=Name(id='deco2'),
                    attr=StrConst(value='attr'),
                ),
                Call(
                    func=Name(id='deco3'),
                    args=[
                        Name(id='arg'),
                    ],
                ),
            ],
        )
        """
        self.assert_dump(funcdef, expected)

    def test_FuncDef_mixed_decorators(self):
        mod = self.parse(
            """
        @mydecorator
        @blue
        @another_deco
        def foo() -> i32:
            return 42
        """
        )
        funcdef = mod.get_funcdef("foo")
        expected = """
        FuncDef(
            color='blue',
            kind='plain',
            name='foo',
            args=[],
            vararg=None,
            return_type=Name(id='i32'),
            docstring=None,
            body=[
                Return(
                    value=Constant(value=42),
                ),
            ],
            decorators=[
                Name(id='mydecorator'),
                Name(id='another_deco'),
            ],
        )
        """
        self.assert_dump(funcdef, expected)

    def test_FuncDef_body(self):
        mod = self.parse(
            """
        def foo() -> i32:
            return 42
        """
        )
        funcdef = mod.get_funcdef("foo")
        expected = """
        FuncDef(
            color='red',
            kind='plain',
            name='foo',
            args=[],
            vararg=None,
            return_type=Name(id='i32'),
            docstring=None,
            body=[
                Return(
                    value=Constant(value=42),
                ),
            ],
            decorators=[],
        )
        """
        self.assert_dump(funcdef, expected)

    def test_FuncDef_docstring(self):
        mod = self.parse(
            """
        def foo() -> i32:
            "hello"
            return 42
        """
        )
        funcdef = mod.get_funcdef("foo")
        expected = """
        FuncDef(
            color='red',
            kind='plain',
            name='foo',
            args=[],
            vararg=None,
            return_type=Name(id='i32'),
            docstring='hello',
            body=[
                Return(
                    value=Constant(value=42),
                ),
            ],
            decorators=[],
        )
        """
        self.assert_dump(funcdef, expected)

    def test_blue_FuncDef(self):
        mod = self.parse(
            """
        @blue
        def foo() -> i32:
            return 42
        """
        )
        funcdef = mod.get_funcdef("foo")
        expected = """
        FuncDef(
            color='blue',
            kind='plain',
            name='foo',
            args=[],
            vararg=None,
            return_type=Name(id='i32'),
            docstring=None,
            body=[
                Return(
                    value=Constant(value=42),
                ),
            ],
            decorators=[],
        )
        """
        self.assert_dump(funcdef, expected)

    def test_blue_generic_FuncDef(self):
        mod = self.parse(
            """
        @blue.generic
        def foo() -> i32:
            return 42
        """
        )
        funcdef = mod.get_funcdef("foo")
        expected = """
        FuncDef(
            color='blue',
            kind='generic',
            name='foo',
            args=[],
            vararg=None,
            return_type=Name(id='i32'),
            docstring=None,
            body=[
                Return(
                    value=Constant(value=42),
                ),
            ],
            decorators=[],
        )
        """
        self.assert_dump(funcdef, expected)

    def test_blue_metafunc_FuncDef(self):
        mod = self.parse(
            """
        @blue.metafunc
        def foo() -> i32:
            return 42
        """
        )
        funcdef = mod.get_funcdef("foo")
        expected = """
        FuncDef(
            color='blue',
            kind='metafunc',
            name='foo',
            args=[],
            vararg=None,
            return_type=Name(id='i32'),
            docstring=None,
            body=[
                Return(
                    value=Constant(value=42),
                ),
            ],
            decorators=[],
        )
        """
        self.assert_dump(funcdef, expected)

    def test_FuncDef_prototype_loc(self):
        # blue functions without return type, are parsed as if they had a
        # synthetic '-> dynamic' annotation. We also need to generate a
        # synthetic Loc for the annotation. This is particularly important
        # because we use return_type.loc to compute prototype_loc, which is
        # used e.g. in error messages.
        mod = self.parse(
            """
        @blue
        def a():
            pass

        @blue
        def b(x):
            pass

        @blue
        def c(
              x):
            pass
        """
        )
        adef = mod.get_funcdef("a")
        bdef = mod.get_funcdef("b")
        cdef = mod.get_funcdef("c")
        assert adef.prototype_loc.get_src() == "def a():"
        assert bdef.prototype_loc.get_src() == "def b(x):"
        assert cdef.prototype_loc.get_src() == "def c(\n      x):"

    def test_empty_return(self):
        mod = self.parse(
            """
        def foo() -> None:
            return
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
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
            "unsupported literal: 42j",
            ("this is not supported yet", "42j"),
        )

    def test_StrConst(self):
        mod = self.parse(
            """
        def foo() -> i32:
            return "hello"
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
        expected = """
        Return(
            value=StrConst(value='hello'),
        )
        """
        self.assert_dump(stmt, expected)

    def test_GetItem(self):
        mod = self.parse(
            """
        def foo() -> None:
            return mylist[0, 1]
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
        expected = """
        Return(
            value=GetItem(
                value=Name(id='mylist'),
                args=[
                    Constant(value=0),
                    Constant(value=1),
                ],
            ),
        )
        """
        self.assert_dump(stmt, expected)

    def test_SetItem(self):
        mod = self.parse(
            """
        def foo() -> None:
            mylist[0, 1] = 42
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
        expected = """
        SetItem(
            target=Name(id='mylist'),
            args=[
                Constant(value=0),
                Constant(value=1),
            ],
            value=Constant(value=42),
        )
        """
        self.assert_dump(stmt, expected)

    def test_VarDef(self):
        mod = self.parse(
            """
        def foo() -> None:
            x: i32 = 42
        """
        )
        vardef, assign = mod.get_funcdef("foo").body[:2]
        vardef_expected = """
        VarDef(
            kind='var',
            name='x',
            type=Name(id='i32'),
        )
        """
        assign_expected = """
        Assign(
            target=StrConst(value='x'),
            value=Constant(value=42),
        )
        """
        self.assert_dump(vardef, vardef_expected)
        self.assert_dump(assign, assign_expected)

    def test_global_VarDef_const(self):
        mod = self.parse(
            """
        x: i32 = 42
        """
        )
        expected = f"""
        Module(
            filename='{self.tmpdir}/test.spy',
            docstring=None,
            decls=[
                GlobalVarDef(
                    vardef=VarDef(
                        kind='const',
                        name='x',
                        type=Name(id='i32'),
                    ),
                    assign=Assign(
                        target=StrConst(value='x'),
                        value=Constant(value=42),
                    ),
                ),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_global_VarDef_var(self):
        mod = self.parse(
            """
        var x: i32 = 42
        """
        )
        expected = f"""
        Module(
            filename='{self.tmpdir}/test.spy',
            docstring=None,
            decls=[
                GlobalVarDef(
                    vardef=VarDef(
                        kind='var',
                        name='x',
                        type=Name(id='i32'),
                    ),
                    assign=Assign(
                        target=StrConst(value='x'),
                        value=Constant(value=42),
                    ),
                ),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_global_VarDef_auto_const(self):
        mod = self.parse(
            """
        x = 42
        """
        )
        expected = f"""
        Module(
            filename='{self.tmpdir}/test.spy',
            docstring=None,
            decls=[
                GlobalVarDef(
                    vardef=VarDef(
                        kind='const',
                        name='x',
                        type=Auto(),
                    ),
                    assign=Assign(
                        target=StrConst(value='x'),
                        value=Constant(value=42),
                    ),
                ),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_global_VarDef_auto_var(self):
        mod = self.parse(
            """
        var x = 42
        """
        )
        expected = f"""
        Module(
            filename='{self.tmpdir}/test.spy',
            docstring=None,
            decls=[
                GlobalVarDef(
                    vardef=VarDef(
                        kind='var',
                        name='x',
                        type=Auto(),
                    ),
                    assign=Assign(
                        target=StrConst(value='x'),
                        value=Constant(value=42),
                    ),
                ),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_List(self):
        mod = self.parse(
            """
        def foo() -> None:
            return [1, 2, 3]
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
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
        mod = self.parse(
            """
        def foo() -> None:
            return 1, 2, 3
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
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
        mod = self.parse(
            f"""
        def foo() -> i32:
            return x {op} 1
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
        expected = f"""
        Return(
            value=BinOp(
                op='{op}',
                left=Name(id='x'),
                right=Constant(value=1),
            ),
        )
        """
        self.assert_dump(stmt, expected)

    @pytest.mark.parametrize("op", "+ - * / // % ** << >> | ^ & @".split())
    def test_AugAssign(self, op):
        mod = self.parse(
            f"""
        def foo() -> None:
            x {op}= 42
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
        expected = f"""
        AugAssign(
            op='{op}',
            target=StrConst(value='x'),
            value=Constant(value=42),
        )
        """
        self.assert_dump(stmt, expected)

    @pytest.mark.parametrize("op", "+ - ~ not".split())
    def test_UnaryOp(self, op):
        mod = self.parse(
            f"""
        def foo() -> i32:
            return {op} x
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
        expected = f"""
        Return(
            value=UnaryOp(
                op='{op}',
                value=Name(id='x'),
            ),
        )
        """
        self.assert_dump(stmt, expected)

    def test_negative_const(self):
        # special case -NUM, so that it's seen as a constant by the rest of
        # the code
        mod = self.parse(
            f"""
        def foo() -> f64:
            return -123 * -1.0
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
        expected = """
        Return(
            value=BinOp(
                op='*',
                left=Constant(value=-123),
                right=Constant(value=-1.0),
            ),
        )
        """
        self.assert_dump(stmt, expected)

    @pytest.mark.parametrize("op", "== != < <= > >= is is_not in not_in".split())
    def test_CompareOp(self, op):
        op = op.replace("_", " ")  # is_not ==> is not
        mod = self.parse(
            f"""
        def foo() -> i32:
            return x {op} 1
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
        expected = f"""
        Return(
            value=CmpOp(
                op='{op}',
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
        mod = self.parse(
            """
        def foo() -> None:
            x = 42
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
        expected = """
        Assign(
            target=StrConst(value='x'),
            value=Constant(value=42),
        )
        """
        self.assert_dump(stmt, expected)

    def test_Assign_unsupported_1(self):
        src = """
        def foo() -> None:
            a = b = 1
        """
        self.expect_errors(
            src,
            "not implemented yet: assign to multiple targets",
            ("this is not supported", "a = b = 1"),
        )

    def test_Assign_unsupported_2(self):
        src = """
        def foo() -> None:
            [a, b] = 1, 2
        """
        self.expect_errors(
            src,
            "not implemented yet: assign to complex expressions",
            ("this is not supported", "[a, b]"),
        )

    def test_UnpackAssign(self):
        mod = self.parse(
            """
        def foo() -> None:
            a, b, c = x
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
        expected = """
        UnpackAssign(
            targets=[
                StrConst(value='a'),
                StrConst(value='b'),
                StrConst(value='c'),
            ],
            value=Name(id='x'),
        )
        """
        self.assert_dump(stmt, expected)

    def test_Call(self):
        mod = self.parse(
            """
        def foo() -> i32:
            return bar(1, 2, 3)
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
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
        mod = self.parse(
            """
        def foo() -> i32:
            return a.b(1, 2)
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
        expected = """
        Return(
            value=CallMethod(
                target=Name(id='a'),
                method=StrConst(value='b'),
                args=[
                    Constant(value=1),
                    Constant(value=2),
                ],
            ),
        )
        """
        self.assert_dump(stmt, expected)

    def test_If(self):
        mod = self.parse(
            """
        def foo() -> i32:
            if x:
                return 1
            else:
                return 2
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
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
        mod = self.parse(
            """
        def foo() -> None:
            42
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
        expected = """
        StmtExpr(
            value=Constant(value=42),
        )
        """
        self.assert_dump(stmt, expected)

    def test_While(self):
        mod = self.parse(
            """
        def foo() -> None:
            while True:
                pass
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
        expected = """
        While(
            test=Constant(value=True),
            body=[
                Pass(),
            ],
        )
        """
        self.assert_dump(stmt, expected)

    def test_For(self):
        mod = self.parse(
            """
        def foo() -> None:
            for i in range(10):
                pass
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
        expected = """
        For(
            seq=0,
            target=StrConst(value='i'),
            iter=Call(
                func=Name(id='range'),
                args=[
                    Constant(value=10),
                ],
            ),
            body=[
                Pass(),
            ],
        )
        """
        self.assert_dump(stmt, expected)

    def test_For_else_unsupported(self):
        src = """
        def foo() -> None:
            for i in range(10):
                pass
            else:
                print("done")
        """
        self.expect_errors(
            src,
            "not implemented yet: `else` clause in `for` loops",
            ("this is not supported", "for"),
        )

    def test_For_complex_target_unsupported(self):
        src = """
        def foo() -> None:
            for i, j in pairs:
                pass
        """
        self.expect_errors(
            src,
            "not implemented yet: complex for loop targets",
            ("this is not supported", "i, j"),
        )

    def test_multiple_For(self):
        mod = self.parse(
            """
        def foo(x: dynamic) -> None:
            for i in x:
                for j in x:
                    pass

            for z in x:
                pass

        """
        )
        body = mod.get_funcdef("foo").body

        # first for loop
        expected0 = """
        For(
            seq=0,
            target=StrConst(value='i'),
            iter=Name(id='x'),
            body=[
                For(
                    seq=1,
                    target=StrConst(value='j'),
                    iter=Name(id='x'),
                    body=[
                        Pass(),
                    ],
                ),
            ],
        )
        """

        # second for loop
        expected1 = """
        For(
            seq=2,
            target=StrConst(value='z'),
            iter=Name(id='x'),
            body=[
                Pass(),
            ],
        )
        """
        self.assert_dump(body[0], expected0)
        self.assert_dump(body[1], expected1)

    def test_Raise(self):
        mod = self.parse(
            """
        def foo() -> None:
            raise ValueError("error message")
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
        expected = """
        Raise(
            exc=Call(
                func=Name(id='ValueError'),
                args=[
                    StrConst(value='error message'),
                ],
            ),
        )
        """
        self.assert_dump(stmt, expected)

    def test_Raise_from(self):
        src = """
        def foo() -> None:
            raise ValueError("error") from TypeError("cause")
        """
        self.expect_errors(
            src,
            "not implemented yet: raise ... from ...",
            (
                "this is not supported",
                'raise ValueError("error") from TypeError("cause")',
            ),
        )

    def test_Raise_bare(self):
        src = """
        def foo() -> None:
            raise
        """
        self.expect_errors(
            src,
            "not implemented yet: bare raise",
            ("this is not supported", "raise"),
        )

    def test_from_import(self):
        mod = self.parse(
            """
        from testmod import a, b as b2
        """
        )
        #
        expected = """
        Module(
            filename='{tmpdir}/test.spy',
            docstring=None,
            decls=[
                Import(ref=<ImportRef testmod.a>, asname='a'),
                Import(ref=<ImportRef testmod.b>, asname='b2'),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_import(self):
        mod = self.parse(
            """
        import aaa
        import bbb as BBB
        import ccc, ddd as DDD
        """
        )
        #
        expected = """
        Module(
            filename='{tmpdir}/test.spy',
            docstring=None,
            decls=[
                Import(ref=<ImportRef aaa>, asname='aaa'),
                Import(ref=<ImportRef bbb>, asname='BBB'),
                Import(ref=<ImportRef ccc>, asname='ccc'),
                Import(ref=<ImportRef ddd>, asname='DDD'),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_module_docstring(self):
        mod = self.parse(
            """
        "hello"
        x = 42
        """
        )

        expected = """
        Module(
            filename='{tmpdir}/test.spy',
            docstring='hello',
            decls=[
                GlobalVarDef(
                    vardef=VarDef(
                        kind='const',
                        name='x',
                        type=Auto(),
                    ),
                    assign=Assign(
                        target=StrConst(value='x'),
                        value=Constant(value=42),
                    ),
                ),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_walk(self):
        def isclass(x: Any, name: str) -> bool:
            return x.__class__.__name__ == name

        mod = self.parse(
            """
        def foo() -> None:
            if True:
                x = y + 1
        """
        )
        nodes: list[Any] = list(mod.walk())
        assert isclass(nodes[0], "Module")
        assert isclass(nodes[1], "GlobalFuncDef")
        assert isclass(nodes[2], "FuncDef")
        assert isclass(nodes[3], "Constant") and nodes[3].value is None
        assert isclass(nodes[4], "If")
        assert isclass(nodes[5], "Constant") and nodes[5].value is True
        assert isclass(nodes[6], "Assign")
        assert isclass(nodes[7], "StrConst") and nodes[7].value == "x"
        assert isclass(nodes[8], "BinOp")
        assert isclass(nodes[9], "Name") and nodes[9].id == "y"
        assert isclass(nodes[10], "Constant") and nodes[10].value == 1
        assert len(nodes) == 11
        #
        nodes2 = list(mod.walk(ast.Stmt))
        expected2 = [node for node in nodes if isinstance(node, ast.Stmt)]
        assert nodes2 == expected2
        #
        nodes3 = list(mod.walk(ast.Expr))
        expected3 = [node for node in nodes if isinstance(node, ast.Expr)]
        assert nodes3 == expected3

    def test_inner_FuncDef(self):
        mod = self.parse(
            """
        @blue
        def foo():
            def bar() -> None:
                pass
        """
        )
        expected = """
        Module(
            filename='{tmpdir}/test.spy',
            docstring=None,
            decls=[
                GlobalFuncDef(
                    funcdef=FuncDef(
                        color='blue',
                        kind='plain',
                        name='foo',
                        args=[],
                        vararg=None,
                        return_type=Name(id='dynamic'),
                        docstring=None,
                        body=[
                            FuncDef(
                                color='red',
                                kind='plain',
                                name='bar',
                                args=[],
                                vararg=None,
                                return_type=Constant(value=None),
                                docstring=None,
                                body=[
                                    Pass(),
                                ],
                                decorators=[],
                            ),
                        ],
                        decorators=[],
                    ),
                ),
            ],
        )
        """
        self.assert_dump(mod, expected)

    def test_GetAttr(self):
        mod = self.parse(
            """
        def foo() -> None:
            a.b
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
        expected = """
        StmtExpr(
            value=GetAttr(
                value=Name(id='a'),
                attr=StrConst(value='b'),
            ),
        )
        """
        self.assert_dump(stmt, expected)

    def test_SetAttr(self):
        mod = self.parse(
            """
        def foo() -> None:
            a.b = 42
        """
        )
        stmt = mod.get_funcdef("foo").body[0]
        expected = """
        SetAttr(
            target=Name(id='a'),
            attr=StrConst(value='b'),
            value=Constant(value=42),
        )
        """
        self.assert_dump(stmt, expected)

    def test_Class(self):
        mod = self.parse(
            """
        class Foo:
            pass
        """
        )
        classdef = mod.get_classdef("Foo")
        expected = """
        ClassDef(
            name='Foo',
            kind='class',
            docstring=None,
            fields=[],
            body=[
                Pass(),
            ],
        )
        """
        self.assert_dump(classdef, expected)

    def test_struct(self):
        mod = self.parse(
            """
        @struct
        class Foo:
            pass
        """
        )
        classdef = mod.get_classdef("Foo")
        expected = """
        ClassDef(
            name='Foo',
            kind='struct',
            docstring=None,
            fields=[],
            body=[
                Pass(),
            ],
        )
        """
        self.assert_dump(classdef, expected)

    def test_Class_docstring(self):
        mod = self.parse(
            """
        class Foo:
            "hello"
            x: i32
        """
        )
        classdef = mod.get_classdef("Foo")

        expected = """
        ClassDef(
            name='Foo',
            kind='class',
            docstring='hello',
            fields=[
                VarDef(
                    kind='var',
                    name='x',
                    type=Name(id='i32'),
                ),
            ],
            body=[],
        )
        """
        self.assert_dump(classdef, expected)

    def test_class_fields(self):
        mod = self.parse(
            """
        @struct
        class Point:
            x: i32
            y: i32
        """
        )
        classdef = mod.get_classdef("Point")
        expected = """
        ClassDef(
            name='Point',
            kind='struct',
            docstring=None,
            fields=[
                VarDef(
                    kind='var',
                    name='x',
                    type=Name(id='i32'),
                ),
                VarDef(
                    kind='var',
                    name='y',
                    type=Name(id='i32'),
                ),
            ],
            body=[],
        )
        """
        self.assert_dump(classdef, expected)

    def test_class_no_assignments(self):
        src = """
        @struct
        class Foo:
            x = 42
        """
        self.expect_errors(
            src,
            "`Assign` not supported inside a classdef",
            ("this is not supported", "x = 42"),
        )

    def test_typelift(self):
        mod = self.parse(
            """
        @typelift
        class Foo:
            __ll__: i32
        """
        )
        classdef = mod.get_classdef("Foo")
        expected = """
        ClassDef(
            name='Foo',
            kind='typelift',
            docstring=None,
            fields=[
                VarDef(
                    kind='var',
                    name='__ll__',
                    type=Name(id='i32'),
                ),
            ],
            body=[],
        )
        """
        self.assert_dump(classdef, expected)

    def test_typelift_and_struct(self):
        src = """
        @typelift
        @struct
        class Foo:
            pass
        """
        self.expect_errors(
            src,
            "cannot use both @struct and @typelift",
            ("this is invalid", "typelift"),
        )

    def test_classdef_methods(self):
        mod = self.parse(
            """
        @typelift
        class Foo:
            __ll__: i32

            def foo() -> None:
                pass
        """
        )
        classdef = mod.get_classdef("Foo")
        expected = """
        ClassDef(
            name='Foo',
            kind='typelift',
            docstring=None,
            fields=[
                VarDef(
                    kind='var',
                    name='__ll__',
                    type=Name(id='i32'),
                ),
            ],
            body=[
                FuncDef(
                    color='red',
                    kind='plain',
                    name='foo',
                    args=[],
                    vararg=None,
                    return_type=Constant(value=None),
                    docstring=None,
                    body=[
                        Pass(),
                    ],
                    decorators=[],
                ),
            ],
        )
        """
        self.assert_dump(classdef, expected)

    def test_vararg(self):
        src = """
        def foo(a: i32, *args: str) -> None:
            pass
        """
        mod = self.parse(src)
        funcdef = mod.get_funcdef("foo")
        expected = """
        FuncDef(
            color='red',
            kind='plain',
            name='foo',
            args=[
                FuncArg(
                    name='a',
                    type=Name(id='i32'),
                ),
            ],
            vararg=FuncArg(
                name='args',
                type=Name(id='str'),
            ),
            return_type=Constant(value=None),
            docstring=None,
            body=[
                Pass(),
            ],
            decorators=[],
        )
        """
        self.assert_dump(funcdef, expected)

    def test_Break(self):
        mod = self.parse(
            """
        def foo() -> None:
            while True:
                break
        """
        )
        while_stmt = mod.get_funcdef("foo").body[0]
        expected = """
        While(
            test=Constant(value=True),
            body=[
                Break(),
            ],
        )
        """
        self.assert_dump(while_stmt, expected)

    def test_Continue(self):
        mod = self.parse(
            """
        def foo() -> None:
            while True:
                continue
        """
        )
        while_stmt = mod.get_funcdef("foo").body[0]
        expected = """
        While(
            test=Constant(value=True),
            body=[
                Continue(),
            ],
        )
        """
        self.assert_dump(while_stmt, expected)

    def test_Break_in_For(self):
        mod = self.parse(
            """
        def foo() -> None:
            for i in range(10):
                if i == 5:
                    break
        """
        )
        for_stmt = mod.get_funcdef("foo").body[0]
        expected = """
        For(
            seq=0,
            target=StrConst(value='i'),
            iter=Call(
                func=Name(id='range'),
                args=[
                    Constant(value=10),
                ],
            ),
            body=[
                If(
                    test=CmpOp(
                        op='==',
                        left=Name(id='i'),
                        right=Constant(value=5),
                    ),
                    then_body=[
                        Break(),
                    ],
                    else_body=[],
                ),
            ],
        )
        """
        self.assert_dump(for_stmt, expected)

    def test_Continue_in_For(self):
        mod = self.parse(
            """
        def foo() -> None:
            for i in range(10):
                if i == 5:
                    continue
        """
        )
        for_stmt = mod.get_funcdef("foo").body[0]
        expected = """
        For(
            seq=0,
            target=StrConst(value='i'),
            iter=Call(
                func=Name(id='range'),
                args=[
                    Constant(value=10),
                ],
            ),
            body=[
                If(
                    test=CmpOp(
                        op='==',
                        left=Name(id='i'),
                        right=Constant(value=5),
                    ),
                    then_body=[
                        Continue(),
                    ],
                    else_body=[],
                ),
            ],
        )
        """
        self.assert_dump(for_stmt, expected)

    def test_and(self):
        mod = self.parse(
            """
        def foo() -> bool:
            return a and b
        """
        )

        stmt = mod.get_funcdef("foo").body[0]

        expected = """
        Return(
            value=And(
                values=[
                    Name(id='a'),
                    Name(id='b'),
                ],
            ),
        )
        """
        self.assert_dump(stmt, expected)

    def test_or(self):
        mod = self.parse(
            """
        def foo() -> bool:
            return a or b
        """
        )

        stmt = mod.get_funcdef("foo").body[0]

        expected = """
        Return(
            value=Or(
                values=[
                    Name(id='a'),
                    Name(id='b'),
                ],
            ),
        )
        """
        self.assert_dump(stmt, expected)

    def test_and_or_combined(self):
        mod = self.parse(
            """
        def foo() -> bool:
            return a or b and c
        """
        )

        stmt = mod.get_funcdef("foo").body[0]

        expected = """
        Return(
            value=Or(
                values=[
                    Name(id='a'),
                    And(
                        values=[
                            Name(id='b'),
                            Name(id='c'),
                        ],
                    ),
                ],
            ),
        )
        """
        self.assert_dump(stmt, expected)
