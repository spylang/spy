#-*- encoding: utf-8 -*-

import pytest
from spy.tests.support import CompilerTest, skip_backends, no_backend

class TestFloat(CompilerTest):

    def test_literal(self):
        mod = self.compile(
        """
        def foo() -> f64:
            return 12.3
        """)
        assert mod.foo() == 12.3

    def test_BinOp(self):
        mod = self.compile(
        """
        def add(x: f64, y: f64) -> f64: return x + y
        def sub(x: f64, y: f64) -> f64: return x - y
        def mul(x: f64, y: f64) -> f64: return x * y
        def div(x: f64, y: f64) -> f64: return x / y
        """)
        assert mod.add(1.5, 2.6) == 4.1
        assert mod.sub(1.5, 0.2) == 1.3
        assert mod.mul(1.5, 0.5) == 0.75
        assert mod.div(1.5, 2.0)   == 0.75

    def test_CompareOp(self):
        mod = self.compile("""
        def cmp_eq (x: f64, y: f64) -> bool: return x == y
        def cmp_neq(x: f64, y: f64) -> bool: return x != y
        def cmp_lt (x: f64, y: f64) -> bool: return x  < y
        def cmp_lte(x: f64, y: f64) -> bool: return x <= y
        def cmp_gt (x: f64, y: f64) -> bool: return x  > y
        def cmp_gte(x: f64, y: f64) -> bool: return x >= y
        """)
        assert mod.cmp_eq(5.1, 5.1) is True
        assert mod.cmp_eq(5.1, 6.2) is False
        #
        assert mod.cmp_neq(5.1, 5.1) is False
        assert mod.cmp_neq(5.1, 6.2) is True
        #
        assert mod.cmp_lt(5.1, 6.2) is True
        assert mod.cmp_lt(5.1, 5.1) is False
        assert mod.cmp_lt(6.2, 5.1) is False
        #
        assert mod.cmp_lte(5.1, 6.2) is True
        assert mod.cmp_lte(5.1, 5.1) is True
        assert mod.cmp_lte(6.2, 5.1) is False
        #
        assert mod.cmp_gt(5.1, 6.2) is False
        assert mod.cmp_gt(5.1, 5.1) is False
        assert mod.cmp_gt(6.2, 5.1) is True
        #
        assert mod.cmp_gte(5.1, 6.2) is False
        assert mod.cmp_gte(5.1, 5.1) is True
        assert mod.cmp_gte(6.2, 5.1) is True
