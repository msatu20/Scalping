"""T23 — Out-of-sample confirmation of the fixed rule TREND_BREAKOUT 4h-n20-k2-r2 (ADR-0012).

    .venv/Scripts/python.exe scripts/confirm_fixed_rule.py --start 2020-02-01 --end 2026-09-30

One fixed rule, no selection: each (symbol, contiguous data segment) is replayed once with
the rule and its zero-cost control; the verdict comes from the pre-registered criteria.
"""

from __future__ import annotations

import argparse
import os
import pickle
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from scalping.backtest import (
    CostModel,
    DataKind,
    FundingSchedule,
    HistoricalStore,
    PriceSource,
    RunSpec,
    SizingParams,
    run_many,
)
from scalping.backtest.research import evaluate_fixed_rule, fixed_rule_report
from scalping.backtest.store import available_segments
from scalping.backtest.walk_forward import TradeRecord
from scalping.config import Settings
from scalping.core import Clock, KlineInterval
from scalping.strategy.signals import SignalHandler, TrendBreakoutParams, TrendBreakoutStrategy

UNIVERSE = (
    "SOLUSDT",
    "ZECUSDT",
    "NEARUSDT",
    "DOGEUSDT",
    "BNBUSDT",
    "UNIUSDT",
    "AVAXUSDT",
    "FILUSDT",
    "AAVEUSDT",
    "DOTUSDT",
    "ALPHAUSDT",
    "DGBUSDT",
    "OCEANUSDT",
    "OMGUSDT",
)
RULE = TrendBreakoutParams(
    interval=KlineInterval.H4, channel=20, trend_ema=200, atr_period=14, atr_mult=2.0, target_r=2.0
)
ZERO_COSTS = CostModel(maker_fee=Decimal(0), taker_fee=Decimal(0), taker_slippage_bps=Decimal(0))
CACHE_VERSION = 1

Job = tuple[str, date, date, str]
JobResult = tuple[str, date, list[TradeRecord], list[TradeRecord], float]


def run_job(job: Job) -> JobResult:
    symbol, start, end, data_dir = job
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    store = HistoricalStore(data_dir)
    sizing = SizingParams(compounding=False, max_leverage=settings.max_leverage)

    def factory(clock: Clock, on_signal: SignalHandler) -> TrendBreakoutStrategy:
        return TrendBreakoutStrategy([symbol], clock, RULE, on_signal)

    specs = [
        RunSpec("rule", factory, CostModel.from_settings(settings), sizing),
        RunSpec("control", factory, ZERO_COSTS, sizing),
    ]
    t0 = time.perf_counter()
    results = run_many(
        store,
        [symbol],
        start,
        end,
        specs,
        price_source=PriceSource.KLINES,
        funding={symbol: FundingSchedule.load(store, symbol)},
        strategy_interval=RULE.interval,
    )
    rule = [TradeRecord.from_trade(t) for t in results["rule"].trades]
    control = [TradeRecord.from_trade(t) for t in results["control"].trades]
    return symbol, start, rule, control, time.perf_counter() - t0


def main(args: argparse.Namespace) -> int:
    store = HistoricalStore(args.data_dir)
    jobs: list[Job] = []
    for s in args.symbols:
        minute = set(available_segments(store, DataKind.KLINES, s, args.start, args.end))
        segs = available_segments(store, DataKind.KLINES, s, args.start, args.end, RULE.interval)
        if not segs:
            print(f"  WARNING {s}: no data")
        for seg in segs:
            if seg in minute and (seg[1] - seg[0]).days >= 30:
                jobs.append((s, seg[0], seg[1], args.data_dir))
            else:
                print(f"  WARNING {s} segment {seg} skipped (short or unmatched 1m data)")
    print(f"{len(jobs)} jobs")

    args.cache_dir.mkdir(parents=True, exist_ok=True)

    def cache(job: Job) -> Path:
        return args.cache_dir / f"v{CACHE_VERSION}_{job[0]}_{job[1]}_{job[2]}.pkl"

    rule: list[TradeRecord] = []
    control: list[TradeRecord] = []
    pending = []
    t0 = time.perf_counter()
    for job in jobs:
        if cache(job).exists():
            with cache(job).open("rb") as fh:  # our own local cache files only
                res: JobResult = pickle.load(fh)
            rule += res[2]
            control += res[3]
            print(f"  {res[0]} {res[1]}: {len(res[2])} trades cached")
        else:
            pending.append(job)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_job, job): job for job in pending}
        for fut in as_completed(futures):
            res = fut.result()
            tmp = cache(futures[fut]).with_suffix(".tmp")
            with tmp.open("wb") as fh:
                pickle.dump(res, fh)
            os.replace(tmp, cache(futures[fut]))
            rule += res[2]
            control += res[3]
            print(f"  {res[0]} {res[1]}: {len(res[2])} trades {res[4] / 60:.1f} min", flush=True)

    criteria = evaluate_fixed_rule(rule)
    for c in criteria:
        print(f"  [{'OK' if c.passed else 'FAIL'}] {c.name}: {c.observed}")
    meta = [
        f"Generado {datetime.now(UTC):%Y-%m-%d %H:%M} UTC por `scripts/confirm_fixed_rule.py` "
        f"({(time.perf_counter() - t0) / 60:.1f} min). Regla fija `{RULE}`; activos "
        f"{', '.join(args.symbols)}; {args.start}..{args.end}; broker sobre velas 1m "
        "(pesimista), costes reales + funding. Pre-registro: ADR-0012.",
    ]
    report = fixed_rule_report(
        "T23 — Confirmación fuera de muestra: TREND_BREAKOUT 4h-n20-k2-r2",
        meta,
        rule,
        control,
        criteria,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    print(f"report: {args.report}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # Windows consoles
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--symbols", nargs="+", type=str.upper, default=list(UNIVERSE))
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/research/t23"))
    default_report = Path("reports/2026-10-15-t23-fixed-rule-confirmation.md")
    parser.add_argument("--report", type=Path, default=default_report)
    sys.exit(main(parser.parse_args()))
