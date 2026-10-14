"""Backtest metrics computed from closed trades (net of fees, slippage and funding)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from scalping.backtest.sim_broker import ClosedTrade


@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    trades: int
    wins: int
    win_rate: float
    gross_pnl: Decimal
    fees: Decimal
    funding: Decimal
    net_pnl: Decimal
    avg_net_per_trade: Decimal
    expectancy_r: float  # mean net R multiple
    profit_factor: float  # gross profits / gross losses (net of costs per trade)
    max_drawdown: Decimal  # peak-to-trough on the closed-trade equity curve
    max_drawdown_pct: float
    initial_equity: Decimal
    final_equity: Decimal
    return_pct: float
    avg_hold_minutes: float
    exit_reasons: dict[str, int]
    fee_to_gross_ratio: float  # fees / |gross pnl|: how much of the edge costs eat


def compute_metrics(trades: Sequence[ClosedTrade], initial_equity: Decimal) -> BacktestMetrics:
    zero = Decimal(0)
    n = len(trades)
    net = [t.net_pnl for t in trades]
    gross = sum((t.gross_pnl for t in trades), zero)
    fees = sum((t.fees for t in trades), zero)
    funding = sum((t.funding for t in trades), zero)
    net_total = sum(net, zero)
    wins = sum(1 for x in net if x > 0)
    profits = sum((x for x in net if x > 0), zero)
    losses = -sum((x for x in net if x < 0), zero)

    equity, peak, max_dd, max_dd_pct = initial_equity, initial_equity, zero, 0.0
    for x in net:
        equity += x
        peak = max(peak, equity)
        drawdown = peak - equity
        if drawdown > max_dd:
            max_dd, max_dd_pct = drawdown, float(drawdown / peak)

    return BacktestMetrics(
        trades=n,
        wins=wins,
        win_rate=wins / n if n else 0.0,
        gross_pnl=gross,
        fees=fees,
        funding=funding,
        net_pnl=net_total,
        avg_net_per_trade=net_total / n if n else zero,
        expectancy_r=float(sum((t.r_multiple for t in trades), zero) / n) if n else 0.0,
        profit_factor=float(profits / losses) if losses else float("inf") if profits else 0.0,
        max_drawdown=max_dd,
        max_drawdown_pct=max_dd_pct,
        initial_equity=initial_equity,
        final_equity=initial_equity + net_total,
        return_pct=float(net_total / initial_equity),
        avg_hold_minutes=sum(t.hold_ms for t in trades) / n / 60_000 if n else 0.0,
        exit_reasons=dict(Counter(t.exit_reason.value for t in trades)),
        fee_to_gross_ratio=float(fees / abs(gross)) if gross else float("inf"),
    )
