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


class ReturnsStats(BaseModel):
    mean: float
    std: float
    skewness: float
    kurtosis: float
    jarque_bera_stat: float
    jarque_bera_pvalue: float
    shapiro_stat: float
    shapiro_pvalue: float


class ReturnsPoint(BaseModel):
    date: date
    simple_return: float
    log_return: float


class ReturnsResponse(BaseModel):
    ticker: str
    points: list[ReturnsPoint]
    stats: ReturnsStats


class IndicatorsPoint(BaseModel):
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
    points: list[IndicatorsPoint]


class VarRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=2, description="Portfolio tickers")
    weights: list[float] = Field(..., min_length=2, description="Portfolio weights")
    confidence: float = Field(default=0.95, ge=0.8, le=0.999)

    @field_validator("tickers")
    @classmethod
    def validate_tickers(cls, value: list[str]) -> list[str]:
        normalized = [t.strip().upper() for t in value]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Tickers must be unique")
        for ticker in normalized:
            if len(ticker) < 1 or len(ticker) > 15:
                raise ValueError(f"Invalid ticker length: {ticker}")
        return normalized

    @field_validator("weights")
    @classmethod
    def validate_weights_sum(cls, value: list[float]) -> list[float]:
        total = sum(value)
        if any(w < 0 for w in value):
            raise ValueError("Weights must be non-negative")
        if abs(total - 1.0) > 1e-4:
            raise ValueError("Weights must sum to 1.0")
        return value


class VarResponse(BaseModel):
    confidence: float
    var_parametric: float
    var_parametric_annualized: float
    var_historical: float
    var_historical_annualized: float
    var_monte_carlo: float
    var_monte_carlo_annualized: float
    cvar_historical: float


class CapmAssetResult(BaseModel):
    ticker: str
    beta: float
    expected_return_capm: float
    annualized_return_asset: float
    annualized_return_market: float
    classification: str


class CapmResponse(BaseModel):
    benchmark: str
    risk_free_rate: float
    assets: list[CapmAssetResult]


class FrontierRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=2)
    n_portfolios: int = Field(default=10000, ge=2000, le=200000)


class FrontierPoint(BaseModel):
    expected_return: float
    volatility: float
    sharpe: float


class PortfolioComposition(BaseModel):
    expected_return: float
    volatility: float
    sharpe: float
    weights: dict[str, float]


class FrontierResponse(BaseModel):
    points: list[FrontierPoint]
    efficient_frontier: list[FrontierPoint]
    min_variance: PortfolioComposition
    max_sharpe: PortfolioComposition


class AlertSignal(BaseModel):
    ticker: str
    signal: str
    reasons: list[str]


class AlertsResponse(BaseModel):
    alerts: list[AlertSignal]


class MacroResponse(BaseModel):
    risk_free_rate_annual: float = Field(..., description="Annual risk free rate as decimal")
    inflation_yoy: float = Field(..., description="YoY inflation as decimal")
    usd_cop: float = Field(..., description="USD/COP exchange rate")


class BenchmarkPerformanceResponse(BaseModel):
    benchmark: str
    portfolio_return_annual: float
    benchmark_return_annual: float
    portfolio_volatility_annual: float
    benchmark_volatility_annual: float
    alpha_jensen: float
    tracking_error: float
    information_ratio: float
    sharpe_portfolio: float
    sharpe_benchmark: float
    max_drawdown_portfolio: float
    max_drawdown_benchmark: float
    cumulative_portfolio_base100: list[float]
    cumulative_benchmark_base100: list[float]


class VolatilityModelResult(BaseModel):
    model_name: str
    log_likelihood: float
    aic: float
    bic: float


class VolatilityResponse(BaseModel):
    ticker: str
    models: list[VolatilityModelResult]
    best_model: str
    forecast_next_day_volatility: float
