from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Proyecto Teoria de Riesgo API"
    app_version: str = "1.0.0"

    # Market data settings
    default_benchmark: str = "SPY"
    default_tickers: list[str] = ["NVDA", "BCOLO.CB", "ECOPETROL.CB", "KO", "SPY"]
    default_start_date: str = "2023-01-01"
    default_end_date: str | None = None

    # Indicator settings
    sma_window: int = Field(default=20, ge=2, le=500)
    ema_window: int = Field(default=20, ge=2, le=500)
    rsi_window: int = Field(default=14, ge=2, le=200)
    bb_window: int = Field(default=20, ge=2, le=500)
    bb_std: float = Field(default=2.0, ge=0.1, le=5.0)
    stoch_window: int = Field(default=14, ge=2, le=200)

    # Risk settings
    default_confidence: float = Field(default=0.95, ge=0.8, le=0.999)
    monte_carlo_sims: int = Field(default=10000, ge=1000, le=200000)
    trading_days_per_year: int = Field(default=252, ge=200, le=366)

    # API keys (optional but supported)
    fred_api_key: str | None = None

    # HTTP and cache settings
    request_timeout_seconds: int = Field(default=15, ge=1, le=120)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
