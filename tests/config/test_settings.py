from decimal import Decimal

import pytest
from pydantic import ValidationError

from scalping.config import HARD_MAX_LEVERAGE, Settings, TradingMode

ENV_VARS = (
    "TRADING_MODE",
    "LIVE_TRADING_CONFIRMED",
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "BINANCE_SECRET",
    "SYMBOLS",
    "MAKER_FEE",
    "TAKER_FEE",
    "MAX_LEVERAGE",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def load() -> Settings:
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_defaults_are_safe() -> None:
    s = load()
    assert s.trading_mode is TradingMode.PAPER
    assert s.symbols == ("BTCUSDT", "ETHUSDT")
    assert (s.maker_fee, s.taker_fee) == (Decimal("0.0002"), Decimal("0.0005"))
    assert s.max_leverage == 3
    assert s.ws_base_url == "wss://fstream.binance.com"


def test_env_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYMBOLS", " btcusdt , ETHUSDT,SOLUSDT ")
    monkeypatch.setenv("MAKER_FEE", "0.00018")
    monkeypatch.setenv("MAX_LEVERAGE", "5")
    s = load()
    assert s.symbols == ("BTCUSDT", "ETHUSDT", "SOLUSDT")
    assert s.maker_fee == Decimal("0.00018")
    assert s.max_leverage == 5


def test_secret_alias_and_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRADING_MODE", "testnet")
    monkeypatch.setenv("BINANCE_API_KEY", "key123")
    monkeypatch.setenv("BINANCE_SECRET", "s3cr3t")
    s = load()
    assert s.binance_api_secret is not None
    assert s.binance_api_secret.get_secret_value() == "s3cr3t"
    assert "s3cr3t" not in repr(s) and "key123" not in repr(s)
    assert s.rest_base_url == "https://testnet.binancefuture.com"


def test_testnet_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRADING_MODE", "testnet")
    with pytest.raises(ValidationError, match="requires BINANCE_API_KEY"):
        load()


def test_live_requires_explicit_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_API_SECRET", "s")
    with pytest.raises(ValidationError, match="LIVE_TRADING_CONFIRMED"):
        load()
    monkeypatch.setenv("LIVE_TRADING_CONFIRMED", "true")
    assert load().trading_mode is TradingMode.LIVE


@pytest.mark.parametrize(
    ("var", "value"),
    [
        ("MAX_LEVERAGE", str(HARD_MAX_LEVERAGE + 1)),
        ("MAX_LEVERAGE", "0"),
        ("TAKER_FEE", "-0.0001"),
        ("TAKER_FEE", "0.05"),  # 5 %: almost certainly a % vs fraction mistake
        ("SYMBOLS", "BTC/USDT"),
        ("SYMBOLS", "BTCUSDT,BTCUSDT"),
        ("SYMBOLS", " , "),
        ("TRADING_MODE", "yolo"),
    ],
)
def test_invalid_values_rejected(monkeypatch: pytest.MonkeyPatch, var: str, value: str) -> None:
    monkeypatch.setenv(var, value)
    with pytest.raises(ValidationError):
        load()


def test_settings_are_immutable() -> None:
    s = load()
    with pytest.raises(ValidationError):
        s.max_leverage = 50  # type: ignore[misc]
