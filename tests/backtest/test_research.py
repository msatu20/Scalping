"""Research report helpers: control split, breakdowns, report sections."""

from datetime import date

from scalping.backtest import day_start_ms
from scalping.backtest.research import breakdown, split_controls, walk_forward_report
from scalping.backtest.walk_forward import Fold, TradeRecord, walk_forward


def rec(day: date, r: float, symbol: str = "BTCUSDT") -> TradeRecord:
    return TradeRecord(symbol, day_start_ms(day) + 1, r, r * 50, 1.0, r > 0)


def test_split_and_breakdown() -> None:
    trades = {"a": [rec(date(2025, 5, 1), 1.0)], "a#nocost": [rec(date(2025, 5, 1), 1.2)]}
    real, control = split_controls(trades)
    assert set(real) == {"a"} and control["a"][0].r == 1.2
    by_year = breakdown(
        [rec(date(2025, 5, 1), 1.0), rec(date(2026, 1, 1), -1.0, "ETHUSDT")], "year"
    )
    assert list(by_year) == ["2025", "2026"]
    assert set(breakdown([rec(date(2025, 5, 1), 1.0, "ETHUSDT")], "symbol")) == {"ETHUSDT"}


def test_report_sections() -> None:
    fold = Fold(date(2026, 1, 1), date(2026, 3, 31), date(2026, 4, 1), date(2026, 4, 30))
    trades = {
        "v1": [rec(date(2026, 2, 1), 0.5)] * 30 + [rec(date(2026, 4, 2), 1.0)] * 3,
        "v1#nocost": [rec(date(2026, 2, 1), 0.6)] * 33,
    }
    report = walk_forward_report(
        "Title", ["meta"], trades, walk_forward({"v1": trades["v1"]}, [fold])
    )
    for section in (
        "# Title",
        "OOS walk-forward (1 tramos)",
        "sin costes (control)",
        "Tramos de test positivos: **1 / 1**",
        "### OOS por símbolo",
        "### OOS por año",
    ):
        assert section in report
    assert walk_forward_report("T", [], {}, walk_forward({}, [fold])).endswith("Sin resultados.\n")


def test_evaluate_criteria() -> None:
    from scalping.backtest.research import criteria_table, evaluate_criteria

    fold = Fold(date(2024, 1, 1), date(2024, 3, 31), date(2024, 4, 1), date(2025, 12, 31))
    good = ([rec(date(2024, 5, 1), 1.0, s) for s in ("A", "B")] * 20
            + [rec(date(2025, 5, 1), -0.5, s) for s in ("A", "B")] * 20
            + [rec(date(2025, 6, 1), 1.0, s) for s in ("A", "B")] * 20)  # fmt: skip
    train = [rec(date(2024, 2, 1), 0.5)] * 30
    wf = walk_forward({"v": train + good}, [fold])
    crit = {c.name: c for c in evaluate_criteria(wf)}
    assert crit["≥ 200 trades OOS"].passed is False  # 120 trades
    assert crit["Años positivos ≥ 70%"].observed == "2/2"
    assert crit["Activos positivos ≥ 60%"].passed
    assert "NO APROBADA" in "\n".join(criteria_table(list(crit.values())))


def test_evaluate_fixed_rule_and_report() -> None:
    from scalping.backtest.research import evaluate_fixed_rule, fixed_rule_report

    recs = ([rec(date(2024, 5, 1), 1.0, s) for s in ("A", "B", "C")] * 40
            + [rec(date(2025, 5, 1), -1.0, s) for s in ("A", "B", "C")] * 20)  # fmt: skip
    crit = {c.name: c for c in evaluate_fixed_rule(recs)}
    assert crit["Mean R > 0 y t ≥ 2"].passed and crit["Profit factor ≥ 1,2"].passed
    assert (
        crit["Años positivos ≥ 70%"].observed == "1/2" and not crit["Años positivos ≥ 70%"].passed
    )
    assert crit["≥ 200 trades"].observed == "180" and not crit["≥ 200 trades"].passed
    text = fixed_rule_report("T", ["m"], recs, recs, list(crit.values()))
    assert "NO APROBADA" in text and "### Por activo" in text and "### Por año" in text
