from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query

from .config import Settings, get_settings
from .dependencies import get_risk_service
from .models import (
    AlertsResponse,
    BenchmarkPerformanceResponse,
    CapmResponse,
    FrontierRequest,
    FrontierResponse,
    IndicatorsResponse,
    MacroResponse,
    PricesResponse,
    ReturnsResponse,
    VarRequest,
    VarResponse,
    VolatilityResponse,
)
from .services import RiskAnalyticsService

app = FastAPI(
    title="Proyecto Teoria del Riesgo API",
    version="1.0.0",
    description="API para analisis de riesgo financiero con FastAPI y Pydantic",
)


@app.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@app.get("/activos", response_model=list[str])
async def activos(settings: Settings = Depends(get_settings)) -> list[str]:
    return settings.default_tickers


@app.get("/precios/{ticker}", response_model=PricesResponse)
async def precios(
    ticker: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    service: RiskAnalyticsService = Depends(get_risk_service),
) -> dict:
    try:
        return await service.prices_async(ticker=ticker.upper(), start=str(start_date) if start_date else None, end=str(end_date) if end_date else None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"External market data provider error: {exc}") from exc


@app.get("/rendimientos/{ticker}", response_model=ReturnsResponse)
async def rendimientos(
    ticker: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    service: RiskAnalyticsService = Depends(get_risk_service),
) -> dict:
    try:
        return await service.returns_async(ticker=ticker.upper(), start=str(start_date) if start_date else None, end=str(end_date) if end_date else None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Error computing returns: {exc}") from exc


@app.get("/indicadores/{ticker}", response_model=IndicatorsResponse)
async def indicadores(
    ticker: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    service: RiskAnalyticsService = Depends(get_risk_service),
) -> dict:
    try:
        return await service.indicators_async(ticker=ticker.upper(), start=str(start_date) if start_date else None, end=str(end_date) if end_date else None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Error computing indicators: {exc}") from exc


@app.post("/var", response_model=VarResponse)
async def var(payload: VarRequest, service: RiskAnalyticsService = Depends(get_risk_service)) -> dict:
    if len(payload.tickers) != len(payload.weights):
        raise HTTPException(status_code=400, detail="Tickers and weights length mismatch")

    try:
        return await service.var_and_cvar_async(payload.tickers, payload.weights, payload.confidence)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Error computing VaR/CVaR: {exc}") from exc


@app.get("/capm", response_model=CapmResponse)
async def capm(
    tickers: str | None = Query(default=None, description="Comma separated tickers"),
    benchmark: str | None = Query(default=None),
    service: RiskAnalyticsService = Depends(get_risk_service),
) -> dict:
    ticker_list = [x.strip().upper() for x in tickers.split(",")] if tickers else None
    try:
        return await service.capm_async(tickers=ticker_list, benchmark=benchmark.upper() if benchmark else None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Error computing CAPM: {exc}") from exc


@app.post("/frontera-eficiente", response_model=FrontierResponse)
async def frontera_eficiente(payload: FrontierRequest, service: RiskAnalyticsService = Depends(get_risk_service)) -> dict:
    try:
        return await service.frontier_async(payload.tickers, payload.n_portfolios)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Error computing efficient frontier: {exc}") from exc


@app.get("/alertas", response_model=AlertsResponse)
async def alertas(
    tickers: str | None = Query(default=None, description="Comma separated tickers"),
    service: RiskAnalyticsService = Depends(get_risk_service),
) -> dict:
    ticker_list = [x.strip().upper() for x in tickers.split(",")] if tickers else None
    try:
        return await service.alerts_async(ticker_list)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Error generating alerts: {exc}") from exc


@app.get("/macro", response_model=MacroResponse)
async def macro(service: RiskAnalyticsService = Depends(get_risk_service)) -> dict:
    try:
        return await service.macro_async()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Error getting macro data: {exc}") from exc


@app.get("/benchmark", response_model=BenchmarkPerformanceResponse)
async def benchmark(
    tickers: str = Query(..., description="Comma separated tickers for portfolio"),
    benchmark: str | None = Query(default=None),
    service: RiskAnalyticsService = Depends(get_risk_service),
) -> dict:
    ticker_list = [x.strip().upper() for x in tickers.split(",") if x.strip()]
    try:
        return await service.benchmark_performance_async(
            tickers=ticker_list,
            benchmark=benchmark.upper() if benchmark else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Error computing benchmark performance: {exc}") from exc


@app.get("/volatilidad/{ticker}", response_model=VolatilityResponse)
async def volatilidad(
    ticker: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    service: RiskAnalyticsService = Depends(get_risk_service),
) -> dict:
    try:
        return await service.volatility_models_async(
            ticker=ticker.upper(),
            start=str(start_date) if start_date else None,
            end=str(end_date) if end_date else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Error fitting volatility models: {exc}") from exc
