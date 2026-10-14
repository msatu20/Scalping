"""T18 — STOP_HUNT_REBOUND walk-forward research (pre-registered in ADR-0009).

    .venv/Scripts/python.exe scripts/research_stop_hunt.py --start 2025-10-13 --end 2026-10-12

Work is split into (symbol x monthly window) jobs; each job replays its window once with
one day of warm-up and evaluates all 16 variants in the same pass (``run_many``), with the
precise TRADES price source. Trades are attributed to the window of their entry time.
"""

from __future__ import annotations

import argparse
import os
import pickle
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from scalping.backtest import (
    CostModel,
    FundingSchedule,
    HistoricalStore,
    PriceSource,
    RunSpec,
    SizingParams,
    day_start_ms,
    run_many,
)
from scalping.backtest.walk_forward import (
    Stats,
    TradeRecord,
    WalkForwardResult,
    add_months,
    make_folds,
    walk_forward,
)
from scalping.config import Settings
from scalping.core import Clock, ExecutionStyle
from scalping.strategy.signals import SignalHandler, StopHuntParams, StopHuntReboundStrategy

SYMBOLS = ("BTCUSDT", "ETHUSDT")
MAKER_OFFSET_BPS = Decimal(2)
ZERO_COSTS = CostModel(maker_fee=Decimal(0), taker_fee=Decimal(0), taker_slippage_bps=Decimal(0))


def grid() -> dict[str, tuple[StopHuntParams, ExecutionStyle]]:
    out = {}
    for lookback in (30, 120):
        for burst_k in (3.0, 6.0):
            for target_r in (1.0, 2.0):
                params = StopHuntParams(lookback_min=lookback, burst_k=burst_k, target_r=target_r)
                for entry in (ExecutionStyle.TAKER, ExecutionStyle.MAKER):
                    name = f"lb{lookback}-k{burst_k:g}-r{target_r:g}-{entry.value.lower()}"
                    out[name] = (params, entry)
    return out


def specs(settings: Settings, symbol: str, zero_costs: bool) -> list[RunSpec]:
    costs = ZERO_COSTS if zero_costs else CostModel.from_settings(settings)
    sizing = SizingParams(compounding=False, max_leverage=settings.max_leverage)
    out = []
    for name, (params, entry) in grid().items():

        def factory(
            clock: Clock, on_signal: SignalHandler, p: StopHuntParams = params
        ) -> StopHuntReboundStrategy:
            return StopHuntReboundStrategy([symbol], clock, p, on_signal)

        offset = MAKER_OFFSET_BPS if entry is ExecutionStyle.MAKER else Decimal(0)
        out.append(RunSpec(name + ("#nocost" if zero_costs else ""), factory, costs, sizing,
                           entry, offset))  # fmt: skip
    return out


Job = tuple[str, date, date, date, date, str, bool]


JobResult = tuple[str, date, dict[str, list[TradeRecord]], dict[str, int], float]
# Bump when the strategy, grid or simulator change: invalidates cached job results.
CACHE_VERSION = 1


def cache_path(cache_dir: Path, job: Job) -> Path:
    symbol, win_start, win_end, _, _, _, with_control = job
    tag = "ctrl" if with_control else "noctrl"
    return cache_dir / f"v{CACHE_VERSION}_{symbol}_{win_start}_{win_end}_{tag}.pkl"


def load_cached(cache_dir: Path, job: Job) -> JobResult | None:
    path = cache_path(cache_dir, job)
    if not path.exists():
        return None
    with path.open("rb") as fh:
        result: JobResult = pickle.load(fh)  # our own local cache files only
    return result


def save_cached(cache_dir: Path, job: Job, result: JobResult) -> None:
    path = cache_path(cache_dir, job)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as fh:
        pickle.dump(result, fh)
    os.replace(tmp, path)


def run_job(job: Job) -> JobResult:
    symbol, win_start, win_end, data_start, data_end, data_dir, with_control = job
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    store = HistoricalStore(data_dir)
    run_from = max(data_start, win_start - timedelta(days=1))  # warm-up
    run_to = min(data_end, win_end + timedelta(days=1))  # let late trades close naturally
    lo, hi = day_start_ms(win_start), day_start_ms(win_end) + 86_400_000
    all_specs = specs(settings, symbol, False) + (
        specs(settings, symbol, True) if with_control else []
    )
    t0 = time.perf_counter()
    results = run_many(store, [symbol], run_from, run_to, all_specs,
                       price_source=PriceSource.TRADES,
                       funding={symbol: FundingSchedule.load(store, symbol)})  # fmt: skip
    trades = {
        name: [TradeRecord.from_trade(t) for t in r.trades if lo <= t.entry.time < hi]
        for name, r in results.items()
    }
    stats: Counter[str] = Counter()
    for name, r in results.items():
        if not name.endswith("#nocost"):
            stats.update(r.skipped)
    return symbol, win_start, trades, dict(stats), time.perf_counter() - t0


def fmt(s: Stats) -> str:
    pf = "inf" if s.profit_factor == float("inf") else f"{s.profit_factor:.2f}"
    return (f"{s.trades} | {s.mean_r:+.3f} | {s.total_r:+.1f} | {s.win_rate:.1%} | {pf} | "
            f"{s.max_drawdown_r:.1f} | {s.t_stat:+.2f}")  # fmt: skip


def write_report(path: Path, args: argparse.Namespace, trades: dict[str, list[TradeRecord]],
                 wf: WalkForwardResult, elapsed: float) -> None:  # fmt: skip
    real = {n: v for n, v in trades.items() if not n.endswith("#nocost")}
    full = {n: Stats.of(sorted(v, key=lambda r: r.entry_time)) for n, v in trades.items()}
    if not real:
        path.write_text("# T18 — sin resultados\n", encoding="utf-8")
        return
    best = max(real, key=lambda n: (full[n].mean_r, full[n].trades))
    header = "trades | mean R | total R | win | PF | max DD (R) | t"
    lines = [
        "# T18 — STOP_HUNT_REBOUND: walk-forward (pre-registrado en ADR-0009)",
        "",
        f"Generado {datetime.now(UTC):%Y-%m-%d %H:%M} UTC por `scripts/research_stop_hunt.py` "
        f"({elapsed / 60:.1f} min). Datos {args.start}..{args.end}, {', '.join(args.symbols)}, "
        "fuente de precio TRADES (aggTrades).",
        "",
        "## Resultado fuera de muestra",
        "",
        f"| | {header} |",
        f"|---|{'---|' * 7}",
        f"| **OOS walk-forward (9 meses)** | {fmt(wf.oos)} |",
        f"| Mejor a posteriori ({best}, IN-SAMPLE, sesgada) | {fmt(full[best])} |",
    ]
    if f"{best}#nocost" in full:
        lines.append(f"| La misma sin costes (control) | {fmt(full[best + '#nocost'])} |")
    lines += ["", "## Tramos", "", "| Test | Variante elegida | Train trades / mean R | "
              "Test trades / mean R / total R |", "|---|---|---|---|"]  # fmt: skip
    for fr in wf.folds:
        lines.append(f"| {fr.fold.test_start}..{fr.fold.test_end} | {fr.selected or '—'} | "
                     f"{fr.train.trades} / {fr.train.mean_r:+.3f} | {fr.test.trades} / "
                     f"{fr.test.mean_r:+.3f} / {fr.test.total_r:+.1f} |")  # fmt: skip
    lines += ["", "## Variantes, periodo completo (IN-SAMPLE, descriptivo)", "",
              f"| Variante | {header} | sin costes: mean R |", f"|---|{'---|' * 8}"]  # fmt: skip
    for name in sorted(real, key=lambda n: -full[n].mean_r):
        control = full.get(f"{name}#nocost")
        ctrl = f"{control.mean_r:+.3f}" if control else "—"
        lines.append(f"| {name} | {fmt(full[name])} | {ctrl} |")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(args: argparse.Namespace) -> int:
    windows = []
    w = args.start
    while w <= args.end:
        nxt = add_months(w, 1)
        windows.append((w, min(args.end, nxt - timedelta(days=1))))
        w = nxt
    if args.max_windows:
        windows = windows[: args.max_windows]
    jobs: list[Job] = [(s, ws, we, args.start, args.end, args.data_dir, not args.no_control)
                       for ws, we in windows for s in args.symbols]  # fmt: skip
    trades: dict[str, list[TradeRecord]] = {}
    skipped: Counter[str] = Counter()
    t0 = time.perf_counter()

    def collect(result: JobResult, done: int, cached: bool) -> None:
        symbol, win_start, job_trades, stats, secs = result
        skipped.update(stats)
        for name, recs in job_trades.items():
            trades.setdefault(name, []).extend(recs)
        n = sum(len(v) for k, v in job_trades.items() if not k.endswith("#nocost"))
        origin = "cached" if cached else f"{secs / 60:.1f} min"
        print(f"  [{done}/{len(jobs)}] {symbol} {win_start}: {n} trades (all variants) "
              f"{origin}", flush=True)  # fmt: skip

    # Resumable: every finished job is cached, so a crash/reboot only loses running jobs.
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    pending: list[Job] = []
    done = 0
    for job in jobs:
        cached = load_cached(args.cache_dir, job) if not args.fresh else None
        if cached is None:
            pending.append(job)
        else:
            done += 1
            collect(cached, done, cached=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_job, job): job for job in pending}
        for fut in as_completed(futures):
            result = fut.result()
            save_cached(args.cache_dir, futures[fut], result)
            done += 1
            collect(result, done, cached=False)
    for recs in trades.values():
        recs.sort(key=lambda r: r.entry_time)
    elapsed = time.perf_counter() - t0
    real = {n: v for n, v in trades.items() if not n.endswith("#nocost")}
    wf = walk_forward(real, make_folds(args.start, args.end), min_train_trades=30)
    print(f"\nOOS: {fmt(wf.oos)}  (trades | mean R | total R | win | PF | maxDD R | t)")
    for fr in wf.folds:
        print(f"  test {fr.fold.test_start}: {fr.selected} -> {fr.test.trades} trades, "
              f"mean {fr.test.mean_r:+.3f} R")  # fmt: skip
    print(f"skips: {dict(skipped)}")
    write_report(args.report, args, trades, wf, elapsed)
    print(f"report: {args.report}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--symbols", nargs="+", type=str.upper, default=list(SYMBOLS))
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    parser.add_argument("--max-windows", type=int, default=0, help="smoke runs: first N windows")
    parser.add_argument("--no-control", action="store_true", help="skip the zero-cost control")
    parser.add_argument("--cache-dir", type=Path, default=Path("data/research/t18"))
    parser.add_argument("--fresh", action="store_true", help="ignore cached job results")
    default_report = Path("reports/2026-10-14-t18-stop-hunt-walk-forward.md")
    parser.add_argument("--report", type=Path, default=default_report)
    sys.exit(main(parser.parse_args()))
