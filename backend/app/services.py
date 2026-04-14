from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache, wraps
from typing import Any

import numpy as np
import pandas as pd
import requests
from arch import arch_model
from requests.adapters import HTTPAdapter
from scipy import stats
from urllib3.util.retry import Retry

from .config import Settings


logger = logging.getLogger(__name__)


def timed(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logger.info("%s executed in %.4f seconds", func.__name__, elapsed)
        return result

    return wrapper


@dataclass
class DataService:
    settings: Settings

    def __post_init__(self) -> None:
        self.session = requests.Session()
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.6,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _epoch_bounds(self, start: str | None, end: str | None) -> tuple[int, int]:
        start_date = pd.to_datetime(start or self.settings.default_start_date)
        end_date = pd.to_datetime(end or datetime.utcnow().date())
        p1 = int(start_date.timestamp())
        p2 = int((end_date + timedelta(days=1)).timestamp())
        return p1, p2

    @timed
    def _fetch_prices_yahoo(self, ticker: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        p1, p2 = self._epoch_bounds(start, end)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        params = {
            "interval": "1d",
            "period1": p1,
            "period2": p2,
            "events": "history",
            "includeAdjustedClose": "true",
        }

        response = self.session.get(url, params=params, timeout=self.settings.request_timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        result = payload.get("chart", {}).get("result", [])
        if not result:
            raise ValueError(f"Yahoo Finance returned no data for {ticker}")

        node = result[0]
        timestamps = node.get("timestamp") or []
        quote = (node.get("indicators", {}).get("quote") or [{}])[0]

        if not timestamps:
            raise ValueError(f"Yahoo Finance timestamps missing for {ticker}")

        frame = pd.DataFrame(
            {
                "date": [datetime.utcfromtimestamp(ts).date() for ts in timestamps],
                "open": quote.get("open", []),
                "high": quote.get("high", []),
                "low": quote.get("low", []),
                "close": quote.get("close", []),
                "volume": quote.get("volume", []),
            }
        )
        frame = frame.dropna(subset=["open", "high", "low", "close"]).copy()
        if frame.empty:
            raise ValueError(f"Yahoo Finance OHLC empty for {ticker}")
        return frame.sort_values("date")

    @timed
    def _fetch_prices_alpha_vantage(self, ticker: str) -> pd.DataFrame:
        if not self.settings.alpha_vantage_api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY not configured")

        url = "https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker,
            "apikey": self.settings.alpha_vantage_api_key,
            "outputsize": "full",
        }
        response = self.session.get(url, params=params, timeout=self.settings.request_timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        series = payload.get("Time Series (Daily)")
        if not series:
            raise ValueError(f"Alpha Vantage returned no series for {ticker}")

        rows = []
        for d, values in series.items():
            rows.append(
                {
                    "date": pd.to_datetime(d).date(),
                    "open": float(values.get("1. open", 0.0)),
                    "high": float(values.get("2. high", 0.0)),
                    "low": float(values.get("3. low", 0.0)),
                    "close": float(values.get("4. close", 0.0)),
                    "volume": float(values.get("6. volume", 0.0)),
                }
            )

        frame = pd.DataFrame(rows).sort_values("date")
        if frame.empty:
            raise ValueError(f"Alpha Vantage OHLC empty for {ticker}")
        return frame

    @timed
    def _fetch_prices_finnhub(self, ticker: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        if not self.settings.finnhub_api_key:
            raise ValueError("FINNHUB_API_KEY not configured")
        p1, p2 = self._epoch_bounds(start, end)

        url = "https://finnhub.io/api/v1/stock/candle"
        params = {
            "symbol": ticker,
            "resolution": "D",
            "from": p1,
            "to": p2,
            "token": self.settings.finnhub_api_key,
        }
        response = self.session.get(url, params=params, timeout=self.settings.request_timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        if payload.get("s") != "ok":
            raise ValueError(f"Finnhub returned status {payload.get('s')} for {ticker}")

        frame = pd.DataFrame(
            {
                "date": [datetime.utcfromtimestamp(ts).date() for ts in payload.get("t", [])],
                "open": payload.get("o", []),
                "high": payload.get("h", []),
                "low": payload.get("l", []),
                "close": payload.get("c", []),
                "volume": payload.get("v", []),
            }
        )
        frame = frame.dropna(subset=["open", "high", "low", "close"]).copy()
        if frame.empty:
            raise ValueError(f"Finnhub OHLC empty for {ticker}")
        return frame.sort_values("date")

    @timed
    def _fetch_prices_polygon(self, ticker: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        if not self.settings.polygon_api_key:
            raise ValueError("POLYGON_API_KEY not configured")

        start_date = (start or self.settings.default_start_date)
        end_date = (end or str(datetime.utcnow().date()))
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
        params = {
            "adjusted": "true",
            "sort": "asc",
            "apiKey": self.settings.polygon_api_key,
            "limit": 50000,
        }
        response = self.session.get(url, params=params, timeout=self.settings.request_timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("results", [])
        if not rows:
            raise ValueError(f"Polygon returned no results for {ticker}")

        frame = pd.DataFrame(
            {
                "date": [datetime.utcfromtimestamp(r["t"] / 1000).date() for r in rows],
                "open": [r.get("o") for r in rows],
                "high": [r.get("h") for r in rows],
                "low": [r.get("l") for r in rows],
                "close": [r.get("c") for r in rows],
                "volume": [r.get("v") for r in rows],
            }
        )
        frame = frame.dropna(subset=["open", "high", "low", "close"]).copy()
        if frame.empty:
            raise ValueError(f"Polygon OHLC empty for {ticker}")
        return frame.sort_values("date")

    def _slice_dates(self, data: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
        out = data.copy()
        if start:
            out = out[out["date"] >= pd.to_datetime(start).date()]
        if end:
            out = out[out["date"] <= pd.to_datetime(end).date()]
        return out.sort_values("date")

    def _provider_sequence(self) -> list[str]:
        ordered = [
            self.settings.market_data_provider,
            "yahoo",
            "alpha_vantage",
            "finnhub",
            "polygon",
        ]
        unique = []
        for provider in ordered:
            if provider and provider not in unique:
                unique.append(provider)
        return unique

    def api_sources_status(self) -> dict[str, Any]:
        return {
            "market_data_provider": self.settings.market_data_provider,
            "provider_fallback_order": self._provider_sequence(),
            "sources": {
                "yahoo_finance": {"enabled": True, "auth": "none"},
                "alpha_vantage": {"enabled": bool(self.settings.alpha_vantage_api_key), "auth": "api_key"},
                "finnhub": {"enabled": bool(self.settings.finnhub_api_key), "auth": "api_key"},
                "polygon": {"enabled": bool(self.settings.polygon_api_key), "auth": "api_key"},
                "fred": {"enabled": True, "auth": "api_key_optional"},
                "banco_republica": {
                    "enabled": bool(self.settings.banrep_enabled),
                    "fx_url_configured": bool(self.settings.banrep_fx_url),
                    "risk_free_url_configured": bool(self.settings.banrep_risk_free_url),
                    "inflation_url_configured": bool(self.settings.banrep_inflation_url),
                },
            },
        }

    @timed
    def fetch_prices_df(self, ticker: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        errors: list[str] = []
        for provider in self._provider_sequence():
            try:
                if provider == "yahoo":
                    frame = self._fetch_prices_yahoo(ticker=ticker, start=start, end=end)
                elif provider == "alpha_vantage":
                    frame = self._slice_dates(self._fetch_prices_alpha_vantage(ticker=ticker), start=start, end=end)
                elif provider == "finnhub":
                    frame = self._fetch_prices_finnhub(ticker=ticker, start=start, end=end)
                elif provider == "polygon":
                    frame = self._fetch_prices_polygon(ticker=ticker, start=start, end=end)
                else:
                    continue

                if not frame.empty:
                    return frame
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{provider}: {exc}")

        raise ValueError(f"No data found for ticker {ticker}. Providers tried -> {' | '.join(errors)}")

    @timed
    def fetch_close_returns_matrix(self, tickers: list[str], start: str | None = None, end: str | None = None) -> pd.DataFrame:
        close_by_ticker: dict[str, pd.Series] = {}
        for ticker in tickers:
            frame = self.fetch_prices_df(ticker=ticker, start=start, end=end)
            close_series = frame.set_index("date")["close"].rename(ticker)
            close_by_ticker[ticker] = close_series

        close = pd.concat(close_by_ticker.values(), axis=1)
        close.columns = list(close_by_ticker.keys())
        close = close.sort_index().dropna(how="all")
        returns = close.pct_change().dropna(how="any")
        if returns.empty:
            raise ValueError("Unable to compute returns matrix")
        return returns

    @lru_cache(maxsize=1)
    @timed
    def get_macro_snapshot(self) -> dict[str, float]:
        rf = self._fetch_fred_latest("DGS10")
        inflation = self._fetch_fred_latest("CPIAUCSL", yoy=True)
        banrep = self._fetch_banrep_snapshot()
        usd_cop = banrep.get("usd_cop") if banrep else None

        if rf is None and banrep:
            rf = banrep.get("risk_free_rate_annual")
        if inflation is None and banrep:
            inflation = banrep.get("inflation_yoy")

        if usd_cop is None:
            usd_cop = self._fetch_usd_cop()

        if rf is None:
            rf = 0.045
        if inflation is None:
            inflation = 0.04
        if usd_cop is None:
            usd_cop = 4000.0

        return {
            "risk_free_rate_annual": float(rf),
            "inflation_yoy": float(inflation),
            "usd_cop": float(usd_cop),
        }

    def _fetch_fred_latest(self, series_id: str, yoy: bool = False) -> float | None:
        base_url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 24,
        }
        if self.settings.fred_api_key:
            params["api_key"] = self.settings.fred_api_key

        try:
            response = self.session.get(base_url, params=params, timeout=self.settings.request_timeout_seconds)
            response.raise_for_status()
            observations = response.json().get("observations", [])
            values = [float(x["value"]) for x in observations if x.get("value") not in {".", None}]
            if not values:
                return None

            if yoy:
                if len(values) < 13:
                    return None
                current = values[0]
                previous_year = values[12]
                return (current / previous_year) - 1.0

            return values[0] / 100.0
        except Exception as exc:  # noqa: BLE001
            logger.warning("FRED call failed for %s: %s", series_id, exc)
            return None

    def _fetch_banrep_snapshot(self) -> dict[str, float] | None:
        # Banco de la Republica endpoints can vary by dataset; these URLs are configurable.
        if not self.settings.banrep_enabled:
            return None

        snapshot: dict[str, float] = {}
        try:
            if self.settings.banrep_fx_url:
                fx_resp = self.session.get(self.settings.banrep_fx_url, timeout=self.settings.request_timeout_seconds)
                fx_resp.raise_for_status()
                fx_payload = fx_resp.json()
                snapshot["usd_cop"] = float(self._extract_first_numeric(fx_payload))
            if self.settings.banrep_risk_free_url:
                rf_resp = self.session.get(self.settings.banrep_risk_free_url, timeout=self.settings.request_timeout_seconds)
                rf_resp.raise_for_status()
                rf_payload = rf_resp.json()
                snapshot["risk_free_rate_annual"] = float(self._extract_first_numeric(rf_payload)) / 100.0
            if self.settings.banrep_inflation_url:
                inf_resp = self.session.get(self.settings.banrep_inflation_url, timeout=self.settings.request_timeout_seconds)
                inf_resp.raise_for_status()
                inf_payload = inf_resp.json()
                snapshot["inflation_yoy"] = float(self._extract_first_numeric(inf_payload)) / 100.0
        except Exception as exc:  # noqa: BLE001
            logger.warning("Banco de la Republica call failed: %s", exc)

        return snapshot or None

    def _extract_first_numeric(self, payload: Any) -> float:
        if isinstance(payload, dict):
            for value in payload.values():
                try:
                    return float(value)
                except Exception:  # noqa: BLE001
                    continue
            for value in payload.values():
                if isinstance(value, (list, dict)):
                    try:
                        return self._extract_first_numeric(value)
                    except Exception:  # noqa: BLE001
                        continue
        if isinstance(payload, list):
            for item in payload:
                try:
                    return self._extract_first_numeric(item)
                except Exception:  # noqa: BLE001
                    continue
        raise ValueError("No numeric value found in payload")

    def _fetch_usd_cop(self) -> float | None:
        # Try Finnhub, then Yahoo chart endpoint.
        if self.settings.finnhub_api_key:
            try:
                p1 = int((datetime.utcnow() - timedelta(days=10)).timestamp())
                p2 = int(datetime.utcnow().timestamp())
                url = "https://finnhub.io/api/v1/forex/candle"
                params = {
                    "symbol": "OANDA:USDCOP",
                    "resolution": "D",
                    "from": p1,
                    "to": p2,
                    "token": self.settings.finnhub_api_key,
                }
                response = self.session.get(url, params=params, timeout=self.settings.request_timeout_seconds)
                response.raise_for_status()
                payload = response.json()
                if payload.get("s") == "ok" and payload.get("c"):
                    return float(payload["c"][-1])
            except Exception as exc:  # noqa: BLE001
                logger.warning("Finnhub USD/COP call failed: %s", exc)

        try:
            data = self._fetch_prices_yahoo("USDCOP=X", start=(datetime.utcnow() - timedelta(days=15)).date().isoformat(), end=datetime.utcnow().date().isoformat())
            return float(data["close"].dropna().iloc[-1])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Yahoo USD/COP call failed: %s", exc)
            return None


@dataclass
class RiskAnalyticsService:
    settings: Settings
    data_service: DataService

    @staticmethod
    def _classification_from_beta(beta: float) -> str:
        if beta > 1.2:
            return "aggressive"
        if beta < 0.8:
            return "defensive"
        return "neutral"

    @timed
    def prices(self, ticker: str, start: str | None = None, end: str | None = None) -> dict:
        df = self.data_service.fetch_prices_df(ticker=ticker, start=start, end=end)
        return {
            "ticker": ticker,
            "start_date": df["date"].iloc[0],
            "end_date": df["date"].iloc[-1],
            "points": df.to_dict(orient="records"),
        }

    @timed
    def returns(self, ticker: str, start: str | None = None, end: str | None = None) -> dict:
        df = self.data_service.fetch_prices_df(ticker=ticker, start=start, end=end)
        df["simple_return"] = df["close"].pct_change()
        df["log_return"] = np.log(df["close"] / df["close"].shift(1))
        out = df.dropna(subset=["simple_return", "log_return"]).copy()

        simple = out["simple_return"]
        jb_stat, jb_pvalue = stats.jarque_bera(simple)
        sample = simple.sample(min(5000, len(simple)), random_state=42)
        shapiro_stat, shapiro_pvalue = stats.shapiro(sample)

        stats_payload = {
            "mean": float(simple.mean()),
            "std": float(simple.std(ddof=1)),
            "skewness": float(simple.skew()),
            "kurtosis": float(simple.kurtosis()),
            "jarque_bera_stat": float(jb_stat),
            "jarque_bera_pvalue": float(jb_pvalue),
            "shapiro_stat": float(shapiro_stat),
            "shapiro_pvalue": float(shapiro_pvalue),
        }

        points = out[["date", "simple_return", "log_return"]].to_dict(orient="records")
        return {"ticker": ticker, "points": points, "stats": stats_payload}

    @timed
    def indicators(self, ticker: str, start: str | None = None, end: str | None = None) -> dict:
        df = self.data_service.fetch_prices_df(ticker=ticker, start=start, end=end)

        close = df["close"]
        high = df["high"]
        low = df["low"]

        sma_w = self.settings.sma_window
        ema_w = self.settings.ema_window
        rsi_w = self.settings.rsi_window
        bb_w = self.settings.bb_window
        bb_std = self.settings.bb_std
        stoch_w = self.settings.stoch_window

        df["sma"] = close.rolling(sma_w).mean()
        df["ema"] = close.ewm(span=ema_w, adjust=False).mean()

        delta = close.diff()
        gain = delta.clip(lower=0).rolling(rsi_w).mean()
        loss = (-delta.clip(upper=0)).rolling(rsi_w).mean()
        rs = gain / loss.replace(0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))

        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df["macd"] = ema12 - ema26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        bb_mid = close.rolling(bb_w).mean()
        bb_sigma = close.rolling(bb_w).std()
        df["bb_mid"] = bb_mid
        df["bb_upper"] = bb_mid + bb_std * bb_sigma
        df["bb_lower"] = bb_mid - bb_std * bb_sigma

        low_min = low.rolling(stoch_w).min()
        high_max = high.rolling(stoch_w).max()
        df["stoch_k"] = 100 * (close - low_min) / (high_max - low_min).replace(0, np.nan)
        df["stoch_d"] = df["stoch_k"].rolling(3).mean()

        points = df[
            [
                "date",
                "close",
                "sma",
                "ema",
                "rsi",
                "macd",
                "macd_signal",
                "macd_hist",
                "bb_upper",
                "bb_mid",
                "bb_lower",
                "stoch_k",
                "stoch_d",
            ]
        ].replace({np.nan: None}).to_dict(orient="records")

        return {"ticker": ticker, "points": points}

    @timed
    def var_and_cvar(self, tickers: list[str], weights: list[float], confidence: float) -> dict:
        returns = self.data_service.fetch_close_returns_matrix(tickers)
        w = np.array(weights)

        portfolio_returns = returns.values @ w
        alpha = 1.0 - confidence

        mu = float(np.mean(portfolio_returns))
        sigma = float(np.std(portfolio_returns, ddof=1))
        z = stats.norm.ppf(alpha)

        var_parametric = float(max(0.0, -(mu + z * sigma)))
        var_historical = float(max(0.0, -np.quantile(portfolio_returns, alpha)))

        threshold = np.quantile(portfolio_returns, alpha)
        tail = portfolio_returns[portfolio_returns <= threshold]
        cvar_historical = float(max(0.0, -tail.mean())) if len(tail) else var_historical

        sims = self.settings.monte_carlo_sims
        mc = np.random.normal(loc=mu, scale=sigma, size=sims)
        var_monte_carlo = float(max(0.0, -np.quantile(mc, alpha)))

        return {
            "confidence": confidence,
            "var_parametric": var_parametric,
            "var_parametric_annualized": float(var_parametric * np.sqrt(self.settings.trading_days_per_year)),
            "var_historical": var_historical,
            "var_historical_annualized": float(var_historical * np.sqrt(self.settings.trading_days_per_year)),
            "var_monte_carlo": var_monte_carlo,
            "var_monte_carlo_annualized": float(var_monte_carlo * np.sqrt(self.settings.trading_days_per_year)),
            "cvar_historical": cvar_historical,
        }

    @timed
    def benchmark_performance(self, tickers: list[str], benchmark: str | None = None) -> dict:
        benchmark_ticker = benchmark or self.settings.default_benchmark
        universe = list(dict.fromkeys(tickers + [benchmark_ticker]))
        returns = self.data_service.fetch_close_returns_matrix(universe)
        rf = self.data_service.get_macro_snapshot()["risk_free_rate_annual"]

        benchmark_series = returns[benchmark_ticker]
        asset_tickers = [t for t in tickers if t in returns.columns and t != benchmark_ticker]
        if not asset_tickers:
            raise ValueError("At least one non-benchmark ticker is required")

        port_series = returns[asset_tickers].mean(axis=1)
        ann = self.settings.trading_days_per_year

        port_ret = float(port_series.mean() * ann)
        bench_ret = float(benchmark_series.mean() * ann)
        port_vol = float(port_series.std(ddof=1) * np.sqrt(ann))
        bench_vol = float(benchmark_series.std(ddof=1) * np.sqrt(ann))

        cov = np.cov(port_series.values, benchmark_series.values, ddof=1)[0, 1]
        var_m = np.var(benchmark_series.values, ddof=1)
        beta_p = float(cov / var_m) if var_m > 0 else 1.0

        alpha_jensen = float(port_ret - (rf + beta_p * (bench_ret - rf)))
        diff = port_series - benchmark_series
        tracking_error = float(diff.std(ddof=1) * np.sqrt(ann))
        information_ratio = float((port_ret - bench_ret) / tracking_error) if tracking_error > 1e-12 else 0.0
        sharpe_port = float((port_ret - rf) / port_vol) if port_vol > 1e-12 else 0.0
        sharpe_bench = float((bench_ret - rf) / bench_vol) if bench_vol > 1e-12 else 0.0

        cumulative_port = (1 + port_series).cumprod() * 100
        cumulative_bench = (1 + benchmark_series).cumprod() * 100

        def max_drawdown(series: pd.Series) -> float:
            running_max = series.cummax()
            dd = (series / running_max) - 1.0
            return float(dd.min())

        return {
            "benchmark": benchmark_ticker,
            "portfolio_return_annual": port_ret,
            "benchmark_return_annual": bench_ret,
            "portfolio_volatility_annual": port_vol,
            "benchmark_volatility_annual": bench_vol,
            "alpha_jensen": alpha_jensen,
            "tracking_error": tracking_error,
            "information_ratio": information_ratio,
            "sharpe_portfolio": sharpe_port,
            "sharpe_benchmark": sharpe_bench,
            "max_drawdown_portfolio": max_drawdown(cumulative_port),
            "max_drawdown_benchmark": max_drawdown(cumulative_bench),
            "cumulative_portfolio_base100": [float(x) for x in cumulative_port.values],
            "cumulative_benchmark_base100": [float(x) for x in cumulative_bench.values],
        }

    @timed
    def capm(self, tickers: list[str] | None = None, benchmark: str | None = None) -> dict:
        asset_tickers = tickers or [t for t in self.settings.default_tickers if t != self.settings.default_benchmark]
        benchmark_ticker = benchmark or self.settings.default_benchmark

        all_tickers = list(dict.fromkeys(asset_tickers + [benchmark_ticker]))
        matrix = self.data_service.fetch_close_returns_matrix(all_tickers)

        if benchmark_ticker not in matrix.columns:
            raise ValueError("Benchmark not available in returns matrix")

        market = matrix[benchmark_ticker]
        rf = self.data_service.get_macro_snapshot()["risk_free_rate_annual"]
        ann_market = float(market.mean() * self.settings.trading_days_per_year)

        assets = []
        for ticker in asset_tickers:
            if ticker not in matrix.columns:
                continue
            series = matrix[ticker]
            slope, _, _, _, _ = stats.linregress(market.values, series.values)
            beta = float(slope)
            ann_asset = float(series.mean() * self.settings.trading_days_per_year)
            expected = float(rf + beta * (ann_market - rf))
            assets.append(
                {
                    "ticker": ticker,
                    "beta": beta,
                    "expected_return_capm": expected,
                    "annualized_return_asset": ann_asset,
                    "annualized_return_market": ann_market,
                    "classification": self._classification_from_beta(beta),
                }
            )

        return {
            "benchmark": benchmark_ticker,
            "risk_free_rate": float(rf),
            "assets": assets,
        }

    @timed
    def frontier(self, tickers: list[str], n_portfolios: int) -> dict:
        returns = self.data_service.fetch_close_returns_matrix(tickers)
        mu = returns.mean().values * self.settings.trading_days_per_year
        cov = returns.cov().values * self.settings.trading_days_per_year
        rf = self.data_service.get_macro_snapshot()["risk_free_rate_annual"]

        n_assets = len(tickers)
        simulations = []

        for _ in range(n_portfolios):
            w = np.random.random(n_assets)
            w = w / w.sum()
            ret = float(np.dot(w, mu))
            vol = float(np.sqrt(np.dot(w.T, np.dot(cov, w))))
            sharpe = (ret - rf) / vol if vol > 0 else 0.0
            simulations.append((ret, vol, sharpe, w))

        points = [{"expected_return": r, "volatility": v, "sharpe": s} for r, v, s, _ in simulations]

        sims_sorted = sorted(simulations, key=lambda x: x[0])
        efficient = []
        best_vol = float("inf")
        for ret, vol, sharpe, w in reversed(sims_sorted):
            if vol < best_vol:
                efficient.append((ret, vol, sharpe, w))
                best_vol = vol
        efficient = list(reversed(efficient))

        min_var = min(simulations, key=lambda x: x[1])
        max_sharpe = max(simulations, key=lambda x: x[2])

        def build_portfolio(entry: tuple[float, float, float, np.ndarray]) -> dict:
            ret, vol, sharpe, w = entry
            return {
                "expected_return": float(ret),
                "volatility": float(vol),
                "sharpe": float(sharpe),
                "weights": {ticker: float(weight) for ticker, weight in zip(tickers, w)},
            }

        return {
            "points": points,
            "efficient_frontier": [
                {"expected_return": r, "volatility": v, "sharpe": s} for r, v, s, _ in efficient
            ],
            "min_variance": build_portfolio(min_var),
            "max_sharpe": build_portfolio(max_sharpe),
        }

    @timed
    def alerts(self, tickers: list[str] | None = None) -> dict:
        symbols = tickers or [t for t in self.settings.default_tickers if t != self.settings.default_benchmark]
        alert_list = []

        for ticker in symbols:
            ind = self.indicators(ticker=ticker)
            points = [p for p in ind["points"] if p["rsi"] is not None]
            if len(points) < 3:
                continue

            last = points[-1]
            prev = points[-2]
            reasons = []

            if prev["macd"] is not None and prev["macd_signal"] is not None and last["macd"] is not None and last["macd_signal"] is not None:
                if prev["macd"] <= prev["macd_signal"] and last["macd"] > last["macd_signal"]:
                    reasons.append("MACD bullish crossover")
                if prev["macd"] >= prev["macd_signal"] and last["macd"] < last["macd_signal"]:
                    reasons.append("MACD bearish crossover")

            if last["rsi"] is not None:
                if last["rsi"] > 70:
                    reasons.append("RSI overbought")
                elif last["rsi"] < 30:
                    reasons.append("RSI oversold")

            if last["bb_upper"] is not None and last["close"] > last["bb_upper"]:
                reasons.append("Price above upper Bollinger band")
            if last["bb_lower"] is not None and last["close"] < last["bb_lower"]:
                reasons.append("Price below lower Bollinger band")

            if prev["sma"] is not None and last["sma"] is not None and prev["close"] <= prev["sma"] and last["close"] > last["sma"]:
                reasons.append("Price crossed above SMA")
            if prev["sma"] is not None and last["sma"] is not None and prev["close"] >= prev["sma"] and last["close"] < last["sma"]:
                reasons.append("Price crossed below SMA")

            if last["stoch_k"] is not None and last["stoch_d"] is not None and prev["stoch_k"] is not None and prev["stoch_d"] is not None:
                if prev["stoch_k"] <= prev["stoch_d"] and last["stoch_k"] > last["stoch_d"] and last["stoch_k"] < 20:
                    reasons.append("Stochastic bullish in oversold zone")
                if prev["stoch_k"] >= prev["stoch_d"] and last["stoch_k"] < last["stoch_d"] and last["stoch_k"] > 80:
                    reasons.append("Stochastic bearish in overbought zone")

            signal = "neutral"
            if any("bullish" in r or "oversold" in r or "below lower" in r for r in reasons):
                signal = "buy"
            if any("bearish" in r or "overbought" in r or "above upper" in r for r in reasons):
                signal = "sell" if signal == "neutral" else "mixed"

            alert_list.append({"ticker": ticker, "signal": signal, "reasons": reasons or ["No active signal"]})

        return {"alerts": alert_list}

    @timed
    def macro(self) -> dict:
        return self.data_service.get_macro_snapshot()

    def sources(self) -> dict:
        return self.data_service.api_sources_status()

    @timed
    def volatility_models(self, ticker: str, start: str | None = None, end: str | None = None) -> dict:
        df = self.data_service.fetch_prices_df(ticker=ticker, start=start, end=end)
        returns = np.log(df["close"] / df["close"].shift(1)).dropna() * 100.0

        candidates = {
            "ARCH(1)": arch_model(returns, vol="ARCH", p=1, q=0, dist="normal"),
            "GARCH(1,1)": arch_model(returns, vol="GARCH", p=1, q=1, dist="normal"),
            "EGARCH(1,1)": arch_model(returns, vol="EGARCH", p=1, q=1, dist="normal"),
        }

        model_results = []
        fitted = {}

        for name, model in candidates.items():
            fit = model.fit(disp="off")
            fitted[name] = fit
            model_results.append(
                {
                    "model_name": name,
                    "log_likelihood": float(fit.loglikelihood),
                    "aic": float(fit.aic),
                    "bic": float(fit.bic),
                }
            )

        best = min(model_results, key=lambda x: x["aic"])
        best_fit = fitted[best["model_name"]]
        forecast = best_fit.forecast(horizon=1)
        vol_next = float(np.sqrt(forecast.variance.iloc[-1, 0]) / 100.0)

        std_resid = pd.Series(best_fit.std_resid).dropna()
        jb_stat, jb_pvalue = stats.jarque_bera(std_resid.values)

        return {
            "ticker": ticker,
            "models": model_results,
            "best_model": best["model_name"],
            "forecast_next_day_volatility": vol_next,
            "residuals_jarque_bera_stat": float(jb_stat),
            "residuals_jarque_bera_pvalue": float(jb_pvalue),
            "standardized_residuals": [float(x) for x in std_resid.tail(400).values],
        }

    async def prices_async(self, ticker: str, start: str | None = None, end: str | None = None) -> dict:
        return await asyncio.to_thread(self.prices, ticker, start, end)

    async def returns_async(self, ticker: str, start: str | None = None, end: str | None = None) -> dict:
        return await asyncio.to_thread(self.returns, ticker, start, end)

    async def indicators_async(self, ticker: str, start: str | None = None, end: str | None = None) -> dict:
        return await asyncio.to_thread(self.indicators, ticker, start, end)

    async def var_and_cvar_async(self, tickers: list[str], weights: list[float], confidence: float) -> dict:
        return await asyncio.to_thread(self.var_and_cvar, tickers, weights, confidence)

    async def capm_async(self, tickers: list[str] | None = None, benchmark: str | None = None) -> dict:
        return await asyncio.to_thread(self.capm, tickers, benchmark)

    async def frontier_async(self, tickers: list[str], n_portfolios: int) -> dict:
        return await asyncio.to_thread(self.frontier, tickers, n_portfolios)

    async def alerts_async(self, tickers: list[str] | None = None) -> dict:
        return await asyncio.to_thread(self.alerts, tickers)

    async def macro_async(self) -> dict:
        return await asyncio.to_thread(self.macro)

    async def sources_async(self) -> dict:
        return await asyncio.to_thread(self.sources)

    async def volatility_models_async(self, ticker: str, start: str | None = None, end: str | None = None) -> dict:
        return await asyncio.to_thread(self.volatility_models, ticker, start, end)

    async def benchmark_performance_async(self, tickers: list[str], benchmark: str | None = None) -> dict:
        return await asyncio.to_thread(self.benchmark_performance, tickers, benchmark)
