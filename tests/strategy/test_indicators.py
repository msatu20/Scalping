"""Indicators: batch vs incremental bit-identical parity, reference values, warm-up, peek."""

import math
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from scalping.strategy.indicators import (
    EMA,
    RSI,
    SMA,
    BollingerBands,
    bollinger,
    ema,
    rsi,
    sma,
)
from tests.conftest import BINANCE_FIXTURES

REAL_CLOSES = pd.read_csv(BINANCE_FIXTURES / "btcusdt_1m_closes.csv")["close"].to_numpy()
NAN = float("nan")


def run_incremental(indicator: Any, values: Any) -> list[Any]:
    return [indicator.update(v) for v in values]


def as_float_array(values: list[float | None]) -> np.ndarray:
    return np.array([NAN if v is None else v for v in values], dtype=np.float64)


def assert_bit_identical(batch: np.ndarray, incremental: list[float | None]) -> None:
    inc = as_float_array(incremental)
    assert batch.shape == inc.shape
    # array_equal on the raw bits: stricter than ==, distinguishes 0.0 / -0.0 too.
    assert np.array_equal(batch.view(np.int64), inc.view(np.int64)), (
        f"first mismatch at {np.flatnonzero(batch.view(np.int64) != inc.view(np.int64))[:5]}"
    )


SCALAR_CASES: list[tuple[str, Callable[[Any, int], np.ndarray], Callable[[int], Any]]] = [
    ("sma", sma, SMA),
    ("ema", ema, EMA),
    ("rsi", rsi, RSI),
]


# ------------------------------------------------------------------ bit-identical parity


@pytest.mark.parametrize(("name", "batch_fn", "cls"), SCALAR_CASES)
@pytest.mark.parametrize("period", [1, 2, 5, 9, 14, 20, 50, 200])
def test_parity_on_real_data(name: str, batch_fn: Any, cls: Any, period: int) -> None:
    assert_bit_identical(batch_fn(REAL_CLOSES, period), run_incremental(cls(period), REAL_CLOSES))


@pytest.mark.parametrize("period", [2, 5, 20, 50])
@pytest.mark.parametrize("num_std", [1.0, 2.0, 2.5])
def test_bollinger_parity_on_real_data(period: int, num_std: float) -> None:
    batch = bollinger(REAL_CLOSES, period, num_std)
    values = run_incremental(BollingerBands(period, num_std), REAL_CLOSES)
    for band in ("middle", "upper", "lower"):
        assert_bit_identical(
            getattr(batch, band), [getattr(v, band) if v else None for v in values]
        )


prices = st.lists(
    st.floats(min_value=1e-4, max_value=1e7, allow_nan=False, allow_infinity=False),
    max_size=120,
)


@settings(max_examples=300, deadline=None)
@given(values=prices, period=st.integers(min_value=1, max_value=40))
def test_parity_property(values: list[float], period: int) -> None:
    for _, batch_fn, cls in SCALAR_CASES:
        assert_bit_identical(batch_fn(values, period), run_incremental(cls(period), values))
    batch = bollinger(values, period, 2.0)
    bands = run_incremental(BollingerBands(period, 2.0), values)
    assert_bit_identical(batch.upper, [b.upper if b else None for b in bands])
    assert_bit_identical(batch.lower, [b.lower if b else None for b in bands])


# ------------------------------------------------------------------ peek == update


@settings(max_examples=150, deadline=None)
@given(values=st.lists(st.floats(min_value=1, max_value=1e5), min_size=1, max_size=60),
       period=st.integers(min_value=1, max_value=20))  # fmt: skip
def test_peek_equals_next_update(values: list[float], period: int) -> None:
    for make in (lambda: SMA(period), lambda: EMA(period), lambda: RSI(period),
                 lambda: BollingerBands(period)):  # fmt: skip
        ind = make()
        for v in values:
            before = ind.value
            peeked = ind.peek(v)
            assert ind.value == before  # peek does not mutate
            assert peeked == ind.update(v)


# ------------------------------------------------------------------ reference values


def test_against_pandas_reference() -> None:
    s = pd.Series(REAL_CLOSES)
    np.testing.assert_allclose(sma(s, 20), s.rolling(20).mean(), rtol=1e-12)

    seeded = pd.concat([pd.Series([s[:20].mean()]), s[20:]], ignore_index=True)
    expected_ema = np.concatenate([np.full(19, NAN), seeded.ewm(span=20, adjust=False).mean()])
    np.testing.assert_allclose(ema(s, 20), expected_ema, rtol=1e-12)

    bands = bollinger(s, 20, 2.0)
    std = s.rolling(20).std(ddof=0)
    np.testing.assert_allclose(bands.upper, s.rolling(20).mean() + 2 * std, rtol=1e-12)
    np.testing.assert_allclose(bands.lower, s.rolling(20).mean() - 2 * std, rtol=1e-12)


def reference_rsi(values: np.ndarray, n: int) -> np.ndarray:
    """Textbook Wilder RSI (100 - 100/(1+RS)), written independently."""
    delta = np.diff(values)
    gains, losses = np.clip(delta, 0, None), np.clip(-delta, 0, None)
    out = np.full(len(values), NAN)
    avg_g, avg_l = gains[:n].mean(), losses[:n].mean()
    for i in range(n, len(values)):
        if i > n:
            avg_g = (avg_g * (n - 1) + gains[i - 1]) / n
            avg_l = (avg_l * (n - 1) + losses[i - 1]) / n
        out[i] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    return out


def test_rsi_against_reference() -> None:
    np.testing.assert_allclose(rsi(REAL_CLOSES, 14), reference_rsi(REAL_CLOSES, 14), rtol=1e-10)


def test_known_small_values() -> None:
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    np.testing.assert_array_equal(sma(x, 3), [NAN, NAN, 2.0, 3.0, 4.0])
    np.testing.assert_array_equal(ema(x, 3), [NAN, NAN, 2.0, 3.0, 4.0])
    np.testing.assert_array_equal(rsi(x, 3), [NAN, NAN, NAN, 100.0, 100.0])
    b = bollinger([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0], 8, 2.0)  # std = 2 exactly
    assert (b.middle[-1], b.upper[-1], b.lower[-1]) == (5.0, 9.0, 1.0)


# ------------------------------------------------------------------ edge cases


def test_warmup_lengths() -> None:
    assert np.isnan(sma(REAL_CLOSES, 20)[:19]).all() and not np.isnan(sma(REAL_CLOSES, 20)[19])
    assert np.isnan(rsi(REAL_CLOSES, 14)[:14]).all() and not np.isnan(rsi(REAL_CLOSES, 14)[14])
    assert np.isnan(sma([1.0, 2.0], 5)).all()


def test_flat_series() -> None:
    flat = [100.0] * 30
    assert set(rsi(flat, 14)[14:]) == {50.0}
    b = bollinger(flat, 20)
    assert (b.upper[-1], b.lower[-1]) == (100.0, 100.0)
    assert BollingerBands(20).peek(100.0) is None


def test_bollinger_value_helpers() -> None:
    bb = BollingerBands(4)
    for v in (1.0, 2.0, 3.0, 4.0):
        bb.update(v)
    assert bb.value is not None
    assert bb.value.percent_b(bb.value.upper) == 1.0
    assert bb.value.percent_b(bb.value.middle) == pytest.approx(0.5)
    assert bb.value.bandwidth == pytest.approx((bb.value.upper - bb.value.lower) / 2.5)


def test_decimal_inputs_match_float_inputs() -> None:
    decimals = [Decimal(str(v)) for v in REAL_CLOSES[:100]]
    assert_bit_identical(ema(decimals, 9), run_incremental(EMA(9), REAL_CLOSES[:100]))


@pytest.mark.parametrize("bad", [0, -1, 2.5, True])
def test_invalid_period(bad: Any) -> None:
    with pytest.raises(ValueError):
        sma([1.0], bad)
    with pytest.raises(ValueError):
        RSI(bad)


@pytest.mark.parametrize("bad", [math.nan, math.inf])
def test_non_finite_values_rejected(bad: float) -> None:
    with pytest.raises(ValueError):
        ema([1.0, bad], 2)
    with pytest.raises(ValueError):
        SMA(2).update(bad)
    with pytest.raises(ValueError):
        bollinger([1.0, 2.0], 2, num_std=bad)
