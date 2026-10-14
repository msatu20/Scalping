"""Shared numeric kernels for indicators.

Parity contract: the batch (numpy) and incremental (scalar) paths perform the same
IEEE-754 operations in the same order, so their results are bit-identical, not just
close. Window sums are therefore accumulated strictly left-to-right in both paths
(never ``np.sum``/``np.mean``, whose pairwise summation order differs), and recursive
indicators share their step functions.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray

type FloatArray = NDArray[np.float64]


def check_period(period: int, minimum: int = 1) -> int:
    if not isinstance(period, int) or isinstance(period, bool) or period < minimum:
        raise ValueError(f"period must be an int >= {minimum}, got {period!r}")
    return period


def as_prices(values: Any) -> FloatArray:
    """1-D finite float64 array (Decimals are converted with correct rounding)."""
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"expected 1-D values, got shape {arr.shape}")
    if not np.isfinite(arr).all():
        raise ValueError("values must be finite (no NaN/inf)")
    return arr


def as_price(value: Any) -> float:
    x = float(value)
    if not math.isfinite(x):
        raise ValueError(f"value must be finite, got {value!r}")
    return x


def nan_array(length: int) -> FloatArray:
    return np.full(length, np.nan, dtype=np.float64)


def window_sums(x: FloatArray, n: int) -> FloatArray:
    """Sum of every length-``n`` window, accumulated left-to-right (vectorised over windows)."""
    view = sliding_window_view(x, n)
    acc = view[:, 0].copy()
    for k in range(1, n):
        acc += view[:, k]
    return acc


def window_sq_dev_sums(x: FloatArray, n: int, means: FloatArray) -> FloatArray:
    """Sum of squared deviations from each window's mean, left-to-right."""
    view = sliding_window_view(x, n)
    d = view[:, 0] - means
    acc = d * d
    for k in range(1, n):
        d = view[:, k] - means
        acc += d * d
    return acc


def scalar_sum(window: Iterable[float]) -> float:
    """Left-to-right sum; scalar twin of ``window_sums``."""
    it = iter(window)
    acc = next(it)
    for v in it:
        acc += v
    return acc


def scalar_sq_dev_sum(window: Iterable[float], mean: float) -> float:
    """Scalar twin of ``window_sq_dev_sums``."""
    it = iter(window)
    d = next(it) - mean
    acc = d * d
    for v in it:
        d = v - mean
        acc += d * d
    return acc
