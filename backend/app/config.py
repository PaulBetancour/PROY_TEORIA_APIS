from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Proyecto Teoria del Riesgo API"
    app_version: str = "1.0.0"

    default_tickers: list[str] = ["NVDA", "CIB", "EC", "KO", "SPY"]
    default_benchmark: str = "SPY"
    history_years: int = Field(default=5, ge=2, le=20)

    # Provider priority: yfinance | yahoo | alpha_vantage | finnhub
    market_data_provider: str = "yfinance"

    # API keys
    fred_api_key: str | None = None
    alpha_vantage_api_key: str | None = None
    finnhub_api_key: str | None = None

    # Risk / indicators params
    default_confidence: float = Field(default=0.95, ge=0.8, le=0.999)
    trading_days: int = Field(default=252, ge=200, le=366)
    monte_carlo_sims: int = Field(default=10000, ge=10000, le=200000)

    sma_window: int = Field(default=20, ge=2, le=300)
    ema_window: int = Field(default=20, ge=2, le=300)
    rsi_window: int = Field(default=14, ge=2, le=100)
    bb_window: int = Field(default=20, ge=2, le=300)
    bb_std: float = Field(default=2.0, ge=0.5, le=4.0)
    stoch_window: int = Field(default=14, ge=2, le=100)

    request_timeout_seconds: int = Field(default=8, ge=3, le=120)
    prices_cache_ttl_seconds: int = Field(default=300, ge=0, le=3600)

    @field_validator("default_tickers", mode="before")
    @classmethod
    def parse_ticker_list(cls, value):
        if isinstance(value, str):
            return [x.strip().upper() for x in value.split(",") if x.strip()]
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
