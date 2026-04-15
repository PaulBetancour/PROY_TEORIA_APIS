from datetime import date

from pydantic import BaseModel, Field, field_validator


class PricePoint(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


class PricesResponse(BaseModel):
    ticker: str
    start_date: date
    end_date: date
    points: list[PricePoint]


class ReturnPoint(BaseModel):
    date: date
    simple_return: float
    log_return: float


class ReturnStats(BaseModel):
    mean: float
    std: float
    skewness: float
    kurtosis: float
    jarque_bera_stat: float
    jarque_bera_pvalue: float
    shapiro_stat: float
    shapiro_pvalue: float


class ReturnsResponse(BaseModel):
    ticker: str
    points: list[ReturnPoint]
    stats: ReturnStats


class IndicatorPoint(BaseModel):
    date: date
    close: float
    sma: float | None = None
    ema: float | None = None
    rsi: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    bb_upper: float | None = None
    bb_mid: float | None = None
    bb_lower: float | None = None
    stoch_k: float | None = None
    stoch_d: float | None = None


class IndicatorsResponse(BaseModel):
    ticker: str
    points: list[IndicatorPoint]


class VarRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=2, description="Tickers del portafolio")
    weights: list[float] = Field(..., min_length=2, description="Pesos por activo")
    confidence: float = Field(default=0.95, ge=0.8, le=0.999)

    @field_validator("tickers")
    @classmethod
    def normalize_tickers(cls, value: list[str]) -> list[str]:
        norm = [t.strip().upper() for t in value]
        if len(set(norm)) != len(norm):
            raise ValueError("Los tickers deben ser unicos")
        return norm

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, value: list[float]) -> list[float]:
        if any(w < 0 for w in value):
            raise ValueError("Los pesos deben ser no negativos")
        total = sum(value)
        if abs(total - 1.0) > 1e-4:
            raise ValueError("Los pesos deben sumar 1.0")
        return value


class VarResponse(BaseModel):
    confidence: float
    var_parametric_daily: float
    var_parametric_annualized: float
    var_historical_daily: float
    var_historical_annualized: float
    var_monte_carlo_daily: float
    var_monte_carlo_annualized: float
    cvar_historical_daily: float
    monte_carlo_simulations: int


class CapmAsset(BaseModel):
    ticker: str
    beta: float
    expected_return_capm: float
    annualized_asset_return: float
    annualized_market_return: float
    classification: str


class CapmResponse(BaseModel):
    benchmark: str
    risk_free_rate: float
    assets: list[CapmAsset]


class FrontierRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=2)
    n_portfolios: int = Field(default=10000, ge=5000, le=200000)


class FrontierPoint(BaseModel):
    expected_return: float
    volatility: float
    sharpe: float


class PortfolioResult(BaseModel):
    expected_return: float
    volatility: float
    sharpe: float
    weights: dict[str, float]


class FrontierResponse(BaseModel):
    points: list[FrontierPoint]
    efficient_frontier: list[FrontierPoint]
    min_variance: PortfolioResult
    max_sharpe: PortfolioResult


class AlertSignal(BaseModel):
    ticker: str
    signal: str
    reasons: list[str]


class AlertsResponse(BaseModel):
    alerts: list[AlertSignal]


class MacroResponse(BaseModel):
    risk_free_rate_annual: float
    inflation_yoy: float
    usd_cop: float


class VolModel(BaseModel):
    model_name: str
    log_likelihood: float
    aic: float
    bic: float


class ResidualPoint(BaseModel):
    date: date
    std_residual: float


class VolatilityPoint(BaseModel):
    date: date
    conditional_volatility: float


class ForecastPoint(BaseModel):
    step: int
    forecast_volatility: float


class VolatilityResponse(BaseModel):
    ticker: str
    models: list[VolModel]
    best_model: str
    forecast_next_day_volatility: float
    forecast_path: list[ForecastPoint]
    residuals: list[ResidualPoint]
    conditional_volatility: list[VolatilityPoint]
    residuals_jarque_bera_stat: float
    residuals_jarque_bera_pvalue: float
