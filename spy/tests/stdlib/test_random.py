"""
Tests for random, seed and uniform (backed by a MT19937 PRNG).

Warning: The `random()` reference values below correspond to the "classic"
MT19937 seeding (single 32-bit `init_genrand`, i.e. NOT CPython's `random.seed()`,
which additionally hashes/spreads the seed via `init_by_array`).
"""

from spy.tests.support import CompilerTest


class TestRandom(CompilerTest):
    def test_random(self):
        src = """
        from random import seed, random

        def seed_with(value: i32) -> None:
            print("seed with", value)
            seed(value)

        def r() -> f64:
            return random()
        """
        mod = self.compile(src)

        mod.seed_with(42)
        a1 = mod.r()
        assert abs(a1 - 0.3745401188473625) < 1e-12
        assert abs(mod.r() - 0.9507143064099162) < 1e-12
        assert abs(mod.r() - 0.7319939418114051) < 1e-12
        assert abs(mod.r() - 0.5986584841970366) < 1e-12
        assert abs(mod.r() - 0.15601864044243652) < 1e-12

        mod.seed_with(1)
        b1 = mod.r()
        assert b1 != a1

        # re-seeding with the same value must reproduce the same stream
        mod.seed_with(42)
        assert abs(mod.r() - 0.3745401188473625) < 1e-12
        assert abs(mod.r() - 0.9507143064099162) < 1e-12
        assert abs(mod.r() - 0.7319939418114051) < 1e-12
        assert abs(mod.r() - 0.5986584841970366) < 1e-12
        assert abs(mod.r() - 0.15601864044243652) < 1e-12

        for s in (0, 1, 2**31 - 1):
            mod.seed_with(s)
            x = mod.r()
            assert 0.0 <= x < 1.0

        values = [mod.r() for _ in range(500)]
        assert all(0.0 <= v < 1.0 for v in values)
        assert len(set(values)) > 1  # not a degenerate/constant generator

    def test_uniform(self):
        src = """
        from random import seed, uniform

        def do_seed() -> None:
            value = 42
            print("seed with", value)
            seed(value)

        def uniform1_10() -> f64:
            return uniform(1.0, 10.0)

        def uniform5() -> f64:
            return uniform(-5.0, 5.0)

        def constant() -> f64:
            return uniform(2.5, 2.5)

        """
        mod = self.compile(src)
        mod.do_seed()

        assert abs(mod.uniform1_10() - 4.370861069626263) < 1e-12
        assert abs(mod.uniform1_10() - 9.556428757689245) < 1e-12
        assert abs(mod.uniform1_10() - 7.587945476302646) < 1e-12
        assert abs(mod.uniform1_10() - 6.387926357773329) < 1e-12
        assert abs(mod.uniform1_10() - 2.4041677639819286) < 1e-12

        values = [mod.uniform5() for _ in range(300)]
        assert all(-5.0 <= v <= 5.0 for v in values)
        assert min(values) < 0.0 < max(values)

        assert mod.constant() == 2.5
