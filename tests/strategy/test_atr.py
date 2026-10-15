"""ATR: batch vs incremental bit-identical, reference values, validation."""

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from scalping.strategy.indicators import ATR, atr

NAN = float("nan")


def incremental(h: list[float], lo: list[float], c: list[float], n: int) -> np.ndarray:
    ind = ATR(n)
    vals = [ind.update(a, b, d) for a, b, d in zip(h, lo, c, strict=True)]
    return np.array([NAN if v is None else v for v in vals])


def bits(a: np.ndarray) -> np.ndarray:
    return np.asarray(a, dtype=np.float64).view(np.int64)


bars = st.lists(
    st.tuples(st.floats(1, 1e5), st.floats(0, 0.05), st.floats(0, 1)), max_size=80
).map(lambda rows: (
    [b * (1 + w) for b, w, _ in rows],
    [b for b, _, _ in rows],
    [b * (1 + w * f) for b, w, f in rows],
))  # fmt: skip


@settings(max_examples=300, deadline=None)
@given(data=bars, n=st.integers(1, 20))
def test_parity_property(data: tuple[list[float], list[float], list[float]], n: int) -> None:
    h, lo, c = data
    assert np.array_equal(bits(atr(h, lo, c, n)), bits(incremental(h, lo, c, n)))


def test_reference_wilder() -> None:
    rng = np.random.default_rng(7)
    c = 100 + np.cumsum(rng.normal(0, 1, 500))
    h, lo = c + rng.uniform(0, 1, 500), c - rng.uniform(0, 1, 500)
    prev = pd.Series(c).shift(1)
    tr = pd.concat([pd.Series(h - lo), (pd.Series(h) - prev).abs(), (pd.Series(lo) - prev).abs()],
                   axis=1).max(axis=1)  # fmt: skip
    expected = np.full(500, NAN)
    expected[14] = tr[1:15].mean()
    for i in range(15, 500):
        expected[i] = (expected[i - 1] * 13 + tr[i]) / 14
    np.testing.assert_allclose(atr(h, lo, c, 14), expected, rtol=1e-12)


def test_known_values_and_warmup() -> None:
    h, lo, c = [11.0, 12.0, 13.0, 15.0], [9.0, 10.0, 11.0, 12.0], [10.0, 11.0, 12.0, 14.0]
    out = atr(h, lo, c, 2)  # TR = [2, 2, 3] -> seed (2+2)/2 = 2, then (2*1+3)/2 = 2.5
    np.testing.assert_array_equal(out, [NAN, NAN, 2.0, 2.5])


def test_validation() -> None:
    with pytest.raises(ValueError):
        atr([1.0], [2.0], [1.5], 1)
    with pytest.raises(ValueError):
        atr([1.0, 2.0], [1.0], [1.0, 2.0], 1)
    with pytest.raises(ValueError):
        ATR(3).update(1.0, 2.0, 1.5)
