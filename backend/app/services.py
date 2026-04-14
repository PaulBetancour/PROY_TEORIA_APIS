from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import date
from functools import lru_cache, wraps

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from arch import arch_model
from scipy import stats

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

    @timed
    def fetch_prices_df(self, ticker: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        start_date = start or self.settings.default_start_date
        end_date = end or self.settings.default_end_date
        data = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=False)
        if data.empty:
            raise ValueError(f"No data found for ticker: {ticker}")
        data = data.reset_index().rename(columns={"Date": "date"})

        required_cols = ["date", "Open", "High", "Low", "Close", "Volume"]
        missing = [col for col in required_cols if col not in data.columns]
        if missing:
            raise ValueError(f"Missing columns in market data for {ticker}: {missing}")

        data = data[required_cols].rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        data["date"] = pd.to_datetime(data["date"]).dt.date
        data = data.dropna().sort_values("date")
        return data

    @timed
    def fetch_close_returns_matrix(self, tickers: list[str], start: str | None = None, end: str | None = None) -> pd.DataFrame:
        start_date = start or self.settings.default_start_date
        end_date = end or self.settings.default_end_date

        raw = yf.download(tickers, start=start_date, end=end_date, progress=False, auto_adjust=False)
        if raw.empty:
            raise ValueError("No price data returned for portfolio")

        if isinstance(raw.columns, pd.MultiIndex):
            if "Close" in raw.columns.get_level_values(0):
                close = raw["Close"].copy()
            else:
                raise ValueError("Close prices not available")
        else:
            close = raw[["Close"]].rename(columns={"Close": tickers[0]})

        close = close.dropna(how="all")
        returns = close.pct_change().dropna(how="any")
        if returns.empty:
            raise ValueError("Unable to compute returns matrix")
        return returns

    @lru_cache(maxsize=1)
    @timed
    def get_macro_snapshot(self) -> dict[str, float]:
        rf = self._fetch_fred_latest("DGS10")
        inflation = self._fetch_fred_latest("CPIAUCSL", yoy=True)
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
            response = requests.get(base_url, params=params, timeout=self.settings.request_timeout_seconds)
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

    def _fetch_usd_cop(self) -> float | None:
        try:
            data = yf.download("USDCOP=X", period="5d", progress=False, auto_adjust=False)
            if data.empty:
                return None
            return float(data["Close"].dropna().iloc[-1])
        except Exception as exc:  # noqa: BLE001
            logger.warning("USD/COP call failed: %s", exc)
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
            "var_historical": var_historical,
            "var_monte_carlo": var_monte_carlo,
            "cvar_historical": cvar_historical,
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

        n_assets = len(tickers)
        simulations = []

        for _ in range(n_portfolios):
            w = np.random.random(n_assets)
            w = w / w.sum()
            ret = float(np.dot(w, mu))
            vol = float(np.sqrt(np.dot(w.T, np.dot(cov, w))))
            sharpe = ret / vol if vol > 0 else 0.0
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
        forecast = fitted[best["model_name"]].forecast(horizon=1)
        vol_next = float(np.sqrt(forecast.variance.iloc[-1, 0]) / 100.0)

        return {
            "ticker": ticker,
            "models": model_results,
            "best_model": best["model_name"],
            "forecast_next_day_volatility": vol_next,
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

    async def volatility_models_async(self, ticker: str, start: str | None = None, end: str | None = None) -> dict:
        return await asyncio.to_thread(self.volatility_models, ticker, start, end)
