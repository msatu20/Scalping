"""T16 — MEAN_REVERSION variants under walk-forward (pre-registered protocol).

    .venv/Scripts/python.exe scripts/research_mean_reversion.py --start 2025-10-13 --end 2026-10-12

Protocol (fixed BEFORE looking at results, see reports/ output):
- 24 variants = timeframe {1m, 5m} x entry {taker, maker -2 bps}
  x stops {structural & R:R >= 1, min 25 bps & R:R >= 0.5, min 40 bps & R:R >= 0.5}
  x regime filter {off, |EMA50 - EMA200| <= 50 bps}.
- Each variant is backtested once over the full period (klines, pessimistic SimBroker,
  real fees + 1 bp slippage + funding, 0.5 % risk without compounding -> results in R).
- Walk-forward: train 3 months -> test 1 month, 9 folds; pick the best train mean R
  (>= 30 train trades); the concatenated test months are the out-of-sample estimate.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from scalping.backtest import (
    Backtester,
    CostModel,
    FundingSchedule,
    HistoricalStore,
    PriceSource,
    SizingParams,
)
from scalping.backtest.walk_forward import (
    Stats,
    TradeRecord,
    WalkForwardResult,
    make_folds,
    walk_forward,
)
from scalping.config import Settings
from scalping.core import Clock, ExecutionStyle, KlineInterval
from scalping.strategy.signals import MeanReversionParams, MeanReversionStrategy, SignalHandler

SYMBOLS = ("BTCUSDT", "ETHUSDT")
MAKER_OFFSET_BPS = Decimal(2)


@dataclass(frozen=True, slots=True)
class Variant:
    name: str
    interval: KlineInterval
    entry: ExecutionStyle
    params: MeanReversionParams


def variants() -> list[Variant]:
    out = []
    for interval, expiry in ((KlineInterval.M1, 180_000), (KlineInterval.M5, 600_000)):
        for entry in (ExecutionStyle.TAKER, ExecutionStyle.MAKER):
            for stop_name, min_stop, min_rr in (("struct", 0.0, 1.0), ("stop25", 25.0, 0.5),
                                                ("stop40", 40.0, 0.5)):  # fmt: skip
                for trend_name, max_trend in (("all", None), ("range", 50.0)):
                    params = MeanReversionParams(
                        interval=interval, expiry_ms=expiry, min_stop_bps=min_stop,
                        min_reward_risk=min_rr, max_trend_bps=max_trend,
                    )  # fmt: skip
                    name = f"{interval}-{entry.value.lower()}-{stop_name}-{trend_name}"
                    out.append(Variant(name, interval, entry, params))
    return out


def run_variant(job: tuple[Variant, str, date, date]) -> tuple[str, list[TradeRecord], int, float]:
    variant, data_dir, start, end = job
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    store = HistoricalStore(data_dir)

    def factory(clock: Clock, on_signal: SignalHandler) -> MeanReversionStrategy:
        return MeanReversionStrategy(SYMBOLS, clock, variant.params, on_signal)

    t0 = time.perf_counter()
    result = Backtester(
        store, SYMBOLS, start, end, factory,
        costs=CostModel.from_settings(settings),
        sizing=SizingParams(compounding=False, max_leverage=settings.max_leverage),
        price_source=PriceSource.KLINES,
        entry_style=variant.entry,
        funding={s: FundingSchedule.load(store, s) for s in SYMBOLS},
        strategy_interval=variant.interval,
        maker_offset_bps=MAKER_OFFSET_BPS if variant.entry is ExecutionStyle.MAKER else Decimal(0),
    ).run()  # fmt: skip
    records = [TradeRecord.from_trade(t) for t in result.trades]
    return variant.name, records, len(result.signals), time.perf_counter() - t0


def fmt(s: Stats) -> str:
    pf = "inf" if s.profit_factor == float("inf") else f"{s.profit_factor:.2f}"
    return (f"{s.trades} | {s.mean_r:+.3f} | {s.total_r:+.1f} | {s.win_rate:.1%} | {pf} | "
            f"{s.max_drawdown_r:.1f} | {s.t_stat:+.2f}")  # fmt: skip


def write_report(
    path: Path,
    args: argparse.Namespace,
    full: dict[str, Stats],
    signals: dict[str, int],
    wf: WalkForwardResult,
    elapsed: float,
) -> None:
    best_name = max(full, key=lambda n: (full[n].mean_r, full[n].trades))
    header = "| trades | mean R | total R | win | PF | max DD (R) | t |"
    lines = [
        "# T16 — MEAN_REVERSION: variantes con walk-forward",
        "",
        f"Generado {datetime.now(UTC):%Y-%m-%d %H:%M} UTC por `scripts/research_mean_reversion.py`"
        f" ({elapsed / 60:.1f} min). Datos {args.start}..{args.end}, {', '.join(SYMBOLS)}.",
        "",
        "## Protocolo (pre-registrado)",
        "",
        *[f"- {line.strip()}" for line in (__doc__ or "").split("Protocol")[1].split("\n- ")[1:]],
        "",
        "## Resultado fuera de muestra (walk-forward)",
        "",
        f"| | {header[2:]}",
        f"|---|{'---|' * 7}",
        f"| **OOS (9 meses de test)** | {fmt(wf.oos)} |",
        f"| Mejor a posteriori ({best_name}, IN-SAMPLE, sesgada) | {fmt(full[best_name])} |",
        "",
        "## Tramos",
        "",
        "| Train | Test | Variante elegida | Train: trades / mean R "
        "| Test: trades / mean R / total R |",
        "|---|---|---|---|---|",
    ]
    for fr in wf.folds:
        f = fr.fold
        lines.append(
            f"| {f.train_start}..{f.train_end} | {f.test_start}..{f.test_end} | "
            f"{fr.selected or '— (ninguna con ≥ 30 trades)'} | "
            f"{fr.train.trades} / {fr.train.mean_r:+.3f} | "
            f"{fr.test.trades} / {fr.test.mean_r:+.3f} / {fr.test.total_r:+.1f} |"
        )
    lines += [
        "",
        "## Todas las variantes, periodo completo (IN-SAMPLE: solo descriptivo)",
        "",
        f"| Variante | señales {header}",
        f"|---|---|{'---|' * 7}",
    ]
    for name in sorted(full, key=lambda n: -full[n].mean_r):
        lines.append(f"| {name} | {signals[name]} | {fmt(full[name])} |")
    lines += ["", "R = PnL neto / riesgo planificado (0,5 % de 10 000 USDT, sin capitalizar). "
              "t = media / error estándar (|t| < 2: no distinguible de 0).", ""]  # fmt: skip
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(args: argparse.Namespace) -> int:
    jobs = [(v, args.data_dir, args.start, args.end) for v in variants()]
    t0 = time.perf_counter()
    trades: dict[str, list[TradeRecord]] = {}
    signals: dict[str, int] = {}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for name, records, n_signals, secs in pool.map(run_variant, jobs):
            trades[name], signals[name] = records, n_signals
            print(f"  {name:<32} {n_signals:>6} signals {len(records):>6} trades  {secs:5.1f}s",
                  flush=True)  # fmt: skip
    elapsed = time.perf_counter() - t0
    full = {name: Stats.of(records) for name, records in trades.items()}
    wf = walk_forward(trades, make_folds(args.start, args.end), min_train_trades=30)

    print(f"\nOOS: {fmt(wf.oos)}  (trades | mean R | total R | win | PF | maxDD R | t)")
    for fr in wf.folds:
        print(f"  test {fr.fold.test_start}: {fr.selected} -> "
              f"{fr.test.trades} trades, mean {fr.test.mean_r:+.3f} R")  # fmt: skip
    write_report(args.report, args, full, signals, wf, elapsed)
    print(f"\nreport: {args.report}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # Windows consoles: cp1252
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    default_report = Path("reports/2026-10-14-t16-mean-reversion-walk-forward.md")
    parser.add_argument("--report", type=Path, default=default_report)
    sys.exit(main(parser.parse_args()))
