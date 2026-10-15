"""data.binance.vision download + Parquet store, against a local HTTP server (no internet)."""

import hashlib
import io
import zipfile
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path

import aiohttp
import pandas as pd
import pytest
from aiohttp import web

from scalping.backtest import (
    BinanceVisionDownloader,
    ChecksumError,
    DataKind,
    DownloadStatus,
    HistoricalStore,
    MissingDataError,
    daily_url,
    find_kline_gaps,
    parse_daily_zip,
    verify_checksum,
)
from scalping.core import KlineInterval

KLINE_HEADER = (
    "open_time,open,high,low,close,volume,close_time,quote_volume,count,"
    "taker_buy_volume,taker_buy_quote_volume,ignore"
)
KLINE_ROWS = [  # real rows, BTCUSDT 2026-10-12
    "1791763200000,83723.10,83739.00,83710.00,83721.60,56.046,1791763259999,4692259.02900,1652,34.756,2909839.29150,0",
    "1791763260000,83721.60,83742.50,83711.70,83711.80,50.234,1791763319999,4205983.79880,1325,24.456,2047616.83380,0",
]  # fmt: skip
AGG_HEADER = "agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker"
AGG_ROWS = [  # real rows, ETHUSDT 2021-01-05
    "108889836,1043.12,1.475,216868847,216868847,1609804800013,true",
    "108889837,1043.11,0.655,216868848,216868848,1609804800013,false",
]

D1, D2, D3 = date(2026, 10, 11), date(2026, 10, 12), date(2026, 10, 13)


def make_zip(lines: list[str], name: str = "data.csv") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(name, "\n".join(lines) + "\n")
    return buf.getvalue()


def checksum_of(payload: bytes) -> str:
    return f"{hashlib.sha256(payload).hexdigest()}  file.zip"


# ------------------------------------------------------------------ parsing


@pytest.mark.parametrize("with_header", [True, False])
def test_parse_klines_with_and_without_header(with_header: bool) -> None:
    lines = [KLINE_HEADER, *KLINE_ROWS] if with_header else KLINE_ROWS
    frame = parse_daily_zip(make_zip(lines), DataKind.KLINES)

    assert len(frame) == 2 and "ignore" not in frame.columns
    assert frame["open_time"].dtype == "int64" and frame["close"].dtype == "float64"
    assert frame.loc[0, "open_time"] == 1791763200000
    assert str(frame.loc[0, "open"]) == "83723.1"  # round-trip exact
    assert frame.loc[1, "count"] == 1325


@pytest.mark.parametrize("with_header", [True, False])
def test_parse_agg_trades(with_header: bool) -> None:
    lines = [AGG_HEADER, *AGG_ROWS] if with_header else AGG_ROWS
    frame = parse_daily_zip(make_zip(lines), DataKind.AGG_TRADES)

    assert frame["is_buyer_maker"].tolist() == [True, False]
    assert frame["price"].tolist() == [1043.12, 1043.11]
    assert frame["transact_time"].dtype == "int64"


def test_microsecond_timestamps_are_normalised_to_ms() -> None:
    row = "1,100.5,0.1,1,1,1609804800013000,true"
    frame = parse_daily_zip(make_zip([row]), DataKind.AGG_TRADES)
    assert frame.loc[0, "transact_time"] == 1609804800013


def test_schema_change_is_rejected() -> None:
    with pytest.raises(ValueError, match="header"):
        parse_daily_zip(make_zip(["open_time,open,EXTRA", *KLINE_ROWS]), DataKind.KLINES)


def test_unsorted_rows_are_rejected() -> None:
    with pytest.raises(ValueError, match="sorted"):
        parse_daily_zip(make_zip(list(reversed(KLINE_ROWS))), DataKind.KLINES)


def test_checksum() -> None:
    payload = make_zip(KLINE_ROWS)
    verify_checksum(payload, checksum_of(payload))
    with pytest.raises(ChecksumError):
        verify_checksum(payload + b"x", checksum_of(payload))
    with pytest.raises(ChecksumError):
        verify_checksum(payload, "")


def test_daily_url() -> None:
    base = "https://data.binance.vision/data/futures/um/daily"
    assert daily_url(DataKind.KLINES, "BTCUSDT", D2) == (
        f"{base}/klines/BTCUSDT/1m/BTCUSDT-1m-2026-10-12.zip"
    )
    assert daily_url(DataKind.AGG_TRADES, "ETHUSDT", D2) == (
        f"{base}/aggTrades/ETHUSDT/ETHUSDT-aggTrades-2026-10-12.zip"
    )


# ------------------------------------------------------------------ store


def test_store_paths_and_missing_days(tmp_path: Path) -> None:
    store = HistoricalStore(tmp_path)
    assert store.path(DataKind.KLINES, "BTCUSDT", D1, KlineInterval.M5) == (
        tmp_path / "futures_um/klines/5m/BTCUSDT/2026-10-11.parquet"
    )
    store.write(pd.DataFrame({"open_time": [1]}), store.path(DataKind.KLINES, "BTCUSDT", D1))
    with pytest.raises(MissingDataError) as err:
        store.load(DataKind.KLINES, "BTCUSDT", D1, D3)
    assert err.value.days == [D2, D3]
    assert not list(tmp_path.rglob("*.tmp"))


def test_find_kline_gaps() -> None:
    frame = pd.DataFrame({"open_time": [0, 60_000, 120_000, 300_000, 360_000]})
    gaps = find_kline_gaps(frame, KlineInterval.M1)
    assert gaps.to_dict("records") == [{"open_time": 120_000, "missing": 2}]


# ------------------------------------------------------------------ downloader


@pytest.fixture
async def vision_server() -> AsyncIterator[tuple[str, dict[str, int]]]:
    good = make_zip([KLINE_HEADER, *KLINE_ROWS])
    corrupt = make_zip(KLINE_ROWS)
    files: dict[str, bytes] = {
        f"/klines/BTCUSDT/1m/BTCUSDT-1m-{D1}.zip": good,
        f"/klines/BTCUSDT/1m/BTCUSDT-1m-{D1}.zip.CHECKSUM": checksum_of(good).encode(),
        f"/klines/BTCUSDT/1m/BTCUSDT-1m-{D2}.zip": good,
        f"/klines/BTCUSDT/1m/BTCUSDT-1m-{D2}.zip.CHECKSUM": checksum_of(good).encode(),
        f"/klines/ETHUSDT/1m/ETHUSDT-1m-{D1}.zip": corrupt,
        f"/klines/ETHUSDT/1m/ETHUSDT-1m-{D1}.zip.CHECKSUM": checksum_of(good).encode(),
    }
    hits: dict[str, int] = {}
    flaky = {"remaining": 1}

    async def handler(request: web.Request) -> web.Response:
        path = request.path
        hits[path] = hits.get(path, 0) + 1
        if path.endswith(f"{D2}.zip") and flaky["remaining"]:
            flaky["remaining"] -= 1
            return web.Response(status=503)
        if path not in files:
            return web.Response(status=404)
        return web.Response(body=files[path])

    app = web.Application()
    app.router.add_get("/{tail:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    yield f"http://127.0.0.1:{runner.addresses[0][1]}", hits
    await runner.cleanup()


async def test_download_range_is_idempotent_and_resilient(
    vision_server: tuple[str, dict[str, int]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_url, hits = vision_server
    monkeypatch.setattr("scalping.backtest.binance_vision.random.uniform", lambda a, b: 0.0)
    store = HistoricalStore(tmp_path)

    async with aiohttp.ClientSession() as session:
        downloader = BinanceVisionDownloader(session, store, base_url=base_url)
        results = await downloader.download_range(["BTCUSDT"], [DataKind.KLINES], D1, D3)
        statuses = {r.day: r.status for r in results}
        assert statuses == {
            D1: DownloadStatus.DOWNLOADED,
            D2: DownloadStatus.DOWNLOADED,  # after one 503 retry
            D3: DownloadStatus.MISSING,  # 404: not published
        }
        assert all(r.rows == 2 for r in results if r.status is DownloadStatus.DOWNLOADED)

        again = await downloader.download_range(["BTCUSDT"], [DataKind.KLINES], D1, D2)
        assert {r.status for r in again} == {DownloadStatus.SKIPPED}

        with pytest.raises(ChecksumError):
            await downloader.download_day(DataKind.KLINES, "ETHUSDT", D1)
        assert not store.has(DataKind.KLINES, "ETHUSDT", D1)  # nothing stored on failure

    assert hits[f"/klines/BTCUSDT/1m/BTCUSDT-1m-{D1}.zip"] == 1  # skipped on second run
    loaded = store.load(DataKind.KLINES, "BTCUSDT", D1, D2)
    assert len(loaded) == 4 and loaded["close"].iloc[0] == 83721.6


def test_resample_klines_ohlc_and_completeness() -> None:
    from scalping.backtest.store import resample_klines

    minute = pd.DataFrame({
        "open_time": [i * 60_000 for i in range(30)],
        "open": [100.0 + i for i in range(30)], "high": [101.0 + i for i in range(30)],
        "low": [99.0 + i for i in range(30)], "close": [100.5 + i for i in range(30)],
        "volume": 1.0, "close_time": [i * 60_000 + 59_999 for i in range(30)],
        "quote_volume": 100.0, "count": 2, "taker_buy_volume": 0.5, "taker_buy_quote_volume": 50.0,
    })  # fmt: skip
    out = resample_klines(minute, KlineInterval.M15)
    assert out["open_time"].tolist() == [0, 900_000]
    assert out.iloc[0][["open", "high", "low", "close"]].tolist() == [100.0, 115.0, 99.0, 114.5]
    assert out.iloc[1]["close_time"] == 1_799_999 and out.iloc[1]["count"] == 30
    with pytest.raises(ValueError, match="incomplete"):
        resample_klines(minute.iloc[:20], KlineInterval.M15)
