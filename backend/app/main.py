from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, get_settings
from .dependencies import get_risk_calculator
from .models import (
    AlertsResponse,
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
from .services import RiskCalculator

app = FastAPI(
    title="Proyecto Teoria del Riesgo API",
    version="1.0.0",
    description="Backend FastAPI para analisis de riesgo financiero",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@app.get("/activos", response_model=list[str])
async def activos(settings: Settings = Depends(get_settings)) -> list[str]:
    return settings.default_tickers


@app.get("/fuentes")
async def fuentes(calc: RiskCalculator = Depends(get_risk_calculator)) -> dict:
    return await calc.sources_async()


@app.get("/precios/{ticker}", response_model=PricesResponse)
async def precios(
    ticker: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    calc: RiskCalculator = Depends(get_risk_calculator),
) -> dict:
    try:
        return await calc.prices_async(ticker=ticker.upper(), start=str(start_date) if start_date else None, end=str(end_date) if end_date else None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Error en proveedor de mercado: {exc}") from exc


@app.get("/rendimientos/{ticker}", response_model=ReturnsResponse)
async def rendimientos(
    ticker: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    calc: RiskCalculator = Depends(get_risk_calculator),
) -> dict:
    try:
        return await calc.returns_async(ticker=ticker.upper(), start=str(start_date) if start_date else None, end=str(end_date) if end_date else None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Error calculando rendimientos: {exc}") from exc


@app.get("/indicadores/{ticker}", response_model=IndicatorsResponse)
async def indicadores(
    ticker: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    calc: RiskCalculator = Depends(get_risk_calculator),
) -> dict:
    try:
        return await calc.indicators_async(ticker=ticker.upper(), start=str(start_date) if start_date else None, end=str(end_date) if end_date else None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Error calculando indicadores: {exc}") from exc


@app.post("/var", response_model=VarResponse)
async def var(payload: VarRequest, calc: RiskCalculator = Depends(get_risk_calculator)) -> dict:
    if len(payload.tickers) != len(payload.weights):
        raise HTTPException(status_code=400, detail="La longitud de tickers y pesos debe coincidir")
    try:
        return await calc.var_cvar_async(payload.tickers, payload.weights, payload.confidence)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Error calculando VaR/CVaR: {exc}") from exc


@app.get("/capm", response_model=CapmResponse)
async def capm(
    tickers: str | None = Query(default=None, description="Tickers separados por coma"),
    benchmark: str | None = Query(default=None),
    calc: RiskCalculator = Depends(get_risk_calculator),
) -> dict:
    tlist = [x.strip().upper() for x in tickers.split(",")] if tickers else None
    try:
        return await calc.capm_async(tickers=tlist, benchmark=benchmark.upper() if benchmark else None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Error calculando CAPM: {exc}") from exc


@app.post("/frontera-eficiente", response_model=FrontierResponse)
async def frontera_eficiente(payload: FrontierRequest, calc: RiskCalculator = Depends(get_risk_calculator)) -> dict:
    try:
        return await calc.frontier_async(payload.tickers, payload.n_portfolios)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Error en Markowitz: {exc}") from exc


@app.get("/alertas", response_model=AlertsResponse)
async def alertas(
    tickers: str | None = Query(default=None, description="Tickers separados por coma"),
    rsi_overbought: float = Query(default=70.0, ge=50.0, le=95.0),
    rsi_oversold: float = Query(default=30.0, ge=5.0, le=50.0),
    stoch_overbought: float = Query(default=80.0, ge=50.0, le=100.0),
    stoch_oversold: float = Query(default=20.0, ge=0.0, le=50.0),
    short_ma_window: int = Query(default=50, ge=5, le=250),
    long_ma_window: int = Query(default=200, ge=20, le=400),
    calc: RiskCalculator = Depends(get_risk_calculator),
) -> dict:
    tlist = [x.strip().upper() for x in tickers.split(",")] if tickers else None
    try:
        return await calc.alerts_async(
            tickers=tlist,
            rsi_overbought=rsi_overbought,
            rsi_oversold=rsi_oversold,
            stoch_overbought=stoch_overbought,
            stoch_oversold=stoch_oversold,
            short_ma_window=short_ma_window,
            long_ma_window=long_ma_window,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Error generando alertas: {exc}") from exc


@app.get("/macro", response_model=MacroResponse)
async def macro(calc: RiskCalculator = Depends(get_risk_calculator)) -> dict:
    try:
        return await calc.macro_async()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Error consultando macro: {exc}") from exc


@app.get("/volatilidad/{ticker}", response_model=VolatilityResponse)
async def volatilidad(
    ticker: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    forecast_steps: int = Query(default=20, ge=5, le=120),
    calc: RiskCalculator = Depends(get_risk_calculator),
) -> dict:
    try:
        return await calc.volatility_models_async(
            ticker=ticker.upper(),
            start=str(start_date) if start_date else None,
            end=str(end_date) if end_date else None,
            forecast_steps=forecast_steps,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Error en modelos de volatilidad: {exc}") from exc
