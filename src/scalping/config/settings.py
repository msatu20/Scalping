"""Runtime settings loaded from environment variables / ``.env`` (pydantic-settings).

Safety rules enforced at load time (ADR-0002, R7):
- default mode is ``paper``;
- ``testnet``/``live`` require API credentials;
- ``live`` additionally requires ``LIVE_TRADING_CONFIRMED=true``;
- leverage is capped by ``HARD_MAX_LEVERAGE`` regardless of configuration.
"""

from __future__ import annotations

import re
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Absolute ceiling; raising it requires a new ADR.
HARD_MAX_LEVERAGE = 10

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{5,20}$")


class TradingMode(StrEnum):
    PAPER = "paper"  # real market data, simulated orders
    TESTNET = "testnet"
    LIVE = "live"


# (REST base, WS base). Verify against official docs periodically (ADR-0004).
_ENDPOINTS: dict[TradingMode, tuple[str, str]] = {
    TradingMode.PAPER: ("https://fapi.binance.com", "wss://fstream.binance.com"),
    TradingMode.TESTNET: ("https://testnet.binancefuture.com", "wss://fstream.binancefuture.com"),
    TradingMode.LIVE: ("https://fapi.binance.com", "wss://fstream.binance.com"),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    trading_mode: TradingMode = TradingMode.PAPER
    live_trading_confirmed: bool = False

    binance_api_key: SecretStr | None = None
    binance_api_secret: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("binance_api_secret", "binance_secret"),
    )

    symbols: Annotated[tuple[str, ...], NoDecode] = ("BTCUSDT", "ETHUSDT")

    maker_fee: Decimal = Field(default=Decimal("0.0002"), ge=0, lt=Decimal("0.01"))
    taker_fee: Decimal = Field(default=Decimal("0.0005"), ge=0, lt=Decimal("0.01"))

    max_leverage: int = Field(default=3, ge=1, le=HARD_MAX_LEVERAGE)

    @field_validator("symbols", mode="before")
    @classmethod
    def _split_symbols(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(s.strip().upper() for s in value.split(",") if s.strip())
        return value

    @field_validator("symbols")
    @classmethod
    def _check_symbols(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("at least one symbol is required")
        invalid = [s for s in value if not _SYMBOL_RE.match(s)]
        if invalid:
            raise ValueError(f"invalid symbols {invalid}; expected Binance format like 'BTCUSDT'")
        if len(set(value)) != len(value):
            raise ValueError("duplicate symbols")
        return value

    @model_validator(mode="after")
    def _check_mode(self) -> Settings:
        if self.trading_mode is not TradingMode.PAPER and not (
            self.binance_api_key and self.binance_api_secret
        ):
            raise ValueError(
                f"{self.trading_mode} mode requires BINANCE_API_KEY and BINANCE_API_SECRET"
            )
        if self.trading_mode is TradingMode.LIVE and not self.live_trading_confirmed:
            raise ValueError("live mode requires LIVE_TRADING_CONFIRMED=true (see ADR-0002)")
        return self

    @property
    def rest_base_url(self) -> str:
        return _ENDPOINTS[self.trading_mode][0]

    @property
    def ws_base_url(self) -> str:
        return _ENDPOINTS[self.trading_mode][1]
