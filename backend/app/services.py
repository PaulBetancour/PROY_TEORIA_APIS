from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache, wraps
from typing import Optional

# Module-level macro cache — DataService is created per-request, so instance-level
# @lru_cache raises TypeError (unhashable) because @dataclass sets __hash__=None.
_macro_cache: Optional[dict] = None
_macro_cache_ts: float = 0.0
_MACRO_CACHE_TTL: float = 600.0  # 10 minutes

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from arch import arch_model
from requests.adapters import HTTPAdapter
from scipy import stats
from urllib3.util.retry import Retry

from .config import Settings


logger = logging.getLogger(__name__)


def timed(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = func(*args, **kwargs)
        dt = time.perf_counter() - t0
        logger.info("%s executed in %.4fs", func.__name__, dt)
        return result

    return wrapper


@dataclass
class DataService:
    settings: Settings

    def __post_init__(self) -> None:
        self.session = requests.Session()
        retries = Retry(
            total=1,
            connect=1,
            read=1,
            backoff_factor=0.2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self._prices_cache: dict[tuple[str, str | None, str | None], tuple[float, pd.DataFrame]] = {}

    def _cache_get_prices(self, ticker: str, start: str | None, end: str | None) -> pd.DataFrame | None:
        ttl = self.settings.prices_cache_ttl_seconds
        if ttl <= 0:
            return None
        key = (ticker, start, end)
        cached = self._prices_cache.get(key)
        if not cached:
            return None
        ts, df = cached
        if (time.time() - ts) > ttl:
            self._prices_cache.pop(key, None)
            return None
        return df.copy()

    def _cache_set_prices(self, ticker: str, start: str | None, end: str | None, df: pd.DataFrame) -> None:
        ttl = self.settings.prices_cache_ttl_seconds
        if ttl <= 0:
            return
        key = (ticker, start, end)
        self._prices_cache[key] = (time.time(), df.copy())

    def _run_with_timeout(self, fn, *args) -> pd.DataFrame:
        # Hard timeout so external providers cannot block a request indefinitely.
        hard_timeout = self.settings.request_timeout_seconds + 2
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(fn, *args)
            return fut.result(timeout=hard_timeout)

    @timed
    def _fetch_prices_yfinance(self, ticker: str, start: str | None, end: str | None) -> pd.DataFrame:
        s, e = self._default_start_end(start, end)
        try:
            raw = yf.download(
                tickers=ticker,
                start=s,
                end=(pd.to_datetime(e) + timedelta(days=1)).date().isoformat(),
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
                timeout=self.settings.request_timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"yfinance fallo para {ticker}: {exc}") from exc

        if raw is None or raw.empty:
            raise ValueError(f"yfinance sin datos para {ticker}")

        # yfinance >= 0.2.45 returns MultiIndex columns even for a single ticker,
        # e.g. ('Open', 'NVDA'), ('Close', 'NVDA').  Flatten to lowercase names.
        df = raw.reset_index()
        if isinstance(df.columns, pd.MultiIndex):
            # level 0 holds the price field name, level 1 holds the ticker symbol
            df.columns = [str(col[0]).lower() for col in df.columns]
        else:
            df.columns = [str(col).lower() for col in df.columns]

        # Normalise the date column (may come as 'date' or 'datetime')
        if "datetime" in df.columns and "date" not in df.columns:
            df = df.rename(columns={"datetime": "date"})

        missing_ohlc = [c for c in ["open", "high", "low", "close"] if c not in df.columns]
        if missing_ohlc:
            raise ValueError(f"yfinance columnas OHLC faltantes para {ticker}: {missing_ohlc}")

        if "volume" not in df.columns:
            df["volume"] = 0.0

        out = df[["date", "open", "high", "low", "close", "volume"]].copy()
        out["date"] = pd.to_datetime(out["date"]).dt.date
        out = out.dropna(subset=["open", "high", "low", "close"]).sort_values("date")
        if out.empty:
            raise ValueError(f"yfinance OHLC vacio para {ticker}")
        return out

    def _default_start_end(self, start: str | None, end: str | None) -> tuple[str, str]:
        end_dt = pd.to_datetime(end).date() if end else datetime.utcnow().date()
        start_dt = pd.to_datetime(start).date() if start else (end_dt - timedelta(days=365 * self.settings.history_years))
        return start_dt.isoformat(), end_dt.isoformat()

    def _epoch_bounds(self, start: str | None, end: str | None) -> tuple[int, int]:
        s, e = self._default_start_end(start, end)
        s_dt = pd.to_datetime(s)
        e_dt = pd.to_datetime(e)
        return int(s_dt.timestamp()), int((e_dt + timedelta(days=1)).timestamp())

    @timed
    def _fetch_prices_yahoo(self, ticker: str, start: str | None, end: str | None) -> pd.DataFrame:
        p1, p2 = self._epoch_bounds(start, end)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        params = {
            "interval": "1d",
            "period1": p1,
            "period2": p2,
            "events": "history",
            "includeAdjustedClose": "true",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }
        resp = self.session.get(url, params=params, headers=headers, timeout=self.settings.request_timeout_seconds)
        resp.raise_for_status()
        payload = resp.json()

        result = payload.get("chart", {}).get("result", [])
        if not result:
            raise ValueError(f"Yahoo sin datos para {ticker}")

        node = result[0]
        ts = node.get("timestamp") or []
        quote = (node.get("indicators", {}).get("quote") or [{}])[0]
        if not ts:
            raise ValueError(f"Yahoo sin timestamps para {ticker}")

        df = pd.DataFrame(
            {
                "date": [datetime.utcfromtimestamp(x).date() for x in ts],
                "open": quote.get("open", []),
                "high": quote.get("high", []),
                "low": quote.get("low", []),
                "close": quote.get("close", []),
                "volume": quote.get("volume", []),
            }
        )
        df = df.dropna(subset=["open", "high", "low", "close"]).copy()
        if df.empty:
            raise ValueError(f"Yahoo OHLC vacio para {ticker}")
        return df.sort_values("date")

    @timed
    def _fetch_prices_alpha_vantage(self, ticker: str, start: str | None, end: str | None) -> pd.DataFrame:
        if not self.settings.alpha_vantage_api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY no configurada")
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker,
            "apikey": self.settings.alpha_vantage_api_key,
            "outputsize": "full",
        }
        resp = self.session.get(url, params=params, timeout=self.settings.request_timeout_seconds)
        resp.raise_for_status()
        payload = resp.json()
        series = payload.get("Time Series (Daily)")
        if not series:
            raise ValueError(f"Alpha Vantage sin datos para {ticker}")

        rows = []
        for d, v in series.items():
            rows.append(
                {
                    "date": pd.to_datetime(d).date(),
                    "open": float(v.get("1. open", 0.0)),
                    "high": float(v.get("2. high", 0.0)),
                    "low": float(v.get("3. low", 0.0)),
                    "close": float(v.get("4. close", 0.0)),
                    "volume": float(v.get("6. volume", 0.0)),
                }
            )
        df = pd.DataFrame(rows).sort_values("date")
        s, e = self._default_start_end(start, end)
        df = df[(df["date"] >= pd.to_datetime(s).date()) & (df["date"] <= pd.to_datetime(e).date())]
        if df.empty:
            raise ValueError(f"Alpha Vantage OHLC vacio para {ticker}")
        return df

    @timed
    def _fetch_prices_finnhub(self, ticker: str, start: str | None, end: str | None) -> pd.DataFrame:
        if not self.settings.finnhub_api_key:
            raise ValueError("FINNHUB_API_KEY no configurada")
        p1, p2 = self._epoch_bounds(start, end)
        url = "https://finnhub.io/api/v1/stock/candle"
        params = {
            "symbol": ticker,
            "resolution": "D",
            "from": p1,
            "to": p2,
            "token": self.settings.finnhub_api_key,
        }
        resp = self.session.get(url, params=params, timeout=self.settings.request_timeout_seconds)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("s") != "ok":
            raise ValueError(f"Finnhub status {payload.get('s')} para {ticker}")

        df = pd.DataFrame(
            {
                "date": [datetime.utcfromtimestamp(x).date() for x in payload.get("t", [])],
                "open": payload.get("o", []),
                "high": payload.get("h", []),
                "low": payload.get("l", []),
                "close": payload.get("c", []),
                "volume": payload.get("v", []),
            }
        )
        df = df.dropna(subset=["open", "high", "low", "close"]).copy()
        if df.empty:
            raise ValueError(f"Finnhub OHLC vacio para {ticker}")
        return df.sort_values("date")

    def _provider_order(self) -> list[str]:
        order = [self.settings.market_data_provider, "yfinance", "yahoo", "alpha_vantage", "finnhub"]
        unique = []
        for p in order:
            if p and p not in unique:
                unique.append(p)
        return unique

    def sources_status(self) -> dict:
        return {
            "provider_priority": self._provider_order(),
            "sources": {
                "yfinance": {"enabled": True, "key_required": False},
                "yahoo_finance": {"enabled": True, "key_required": False},
                "alpha_vantage": {"enabled": bool(self.settings.alpha_vantage_api_key), "key_required": True},
                "finnhub": {"enabled": bool(self.settings.finnhub_api_key), "key_required": True},
                "fred": {"enabled": True, "key_required": False},
            },
        }

    @timed
    def fetch_prices_df(self, ticker: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        cached = self._cache_get_prices(ticker=ticker, start=start, end=end)
        if cached is not None:
            return cached

        errors: list[str] = []
        for provider in self._provider_order():
            try:
                if provider == "yfinance":
                    df = self._run_with_timeout(self._fetch_prices_yfinance, ticker, start, end)
                    self._cache_set_prices(ticker=ticker, start=start, end=end, df=df)
                    return df
                if provider == "yahoo":
                    df = self._run_with_timeout(self._fetch_prices_yahoo, ticker, start, end)
                    self._cache_set_prices(ticker=ticker, start=start, end=end, df=df)
                    return df
                if provider == "alpha_vantage":
                    df = self._run_with_timeout(self._fetch_prices_alpha_vantage, ticker, start, end)
                    self._cache_set_prices(ticker=ticker, start=start, end=end, df=df)
                    return df
                if provider == "finnhub":
                    df = self._run_with_timeout(self._fetch_prices_finnhub, ticker, start, end)
                    self._cache_set_prices(ticker=ticker, start=start, end=end, df=df)
                    return df
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{provider}: {exc}")

        raise ValueError(f"No fue posible obtener datos para {ticker}. {' | '.join(errors)}")

    @timed
    def fetch_close_returns_matrix(self, tickers: list[str], start: str | None = None, end: str | None = None) -> pd.DataFrame:
        series = []
        for t in tickers:
            df = self.fetch_prices_df(t, start, end)
            s = df.set_index("date")["close"].rename(t)
            series.append(s)

        close_df = pd.concat(series, axis=1).sort_index().dropna(how="all")
        rets = close_df.pct_change().dropna(how="any")
        if rets.empty:
            raise ValueError("No fue posible calcular matriz de rendimientos")
        return rets

    @timed
    def _fetch_fred_latest(self, series_id: str, yoy: bool = False) -> float | None:
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 24,
        }
        if self.settings.fred_api_key:
            params["api_key"] = self.settings.fred_api_key

        try:
            resp = self.session.get(url, params=params, timeout=self.settings.request_timeout_seconds)
            resp.raise_for_status()
            obs = resp.json().get("observations", [])
            vals = [float(x["value"]) for x in obs if x.get("value") not in {".", None}]
            if not vals:
                return None
            if yoy:
                if len(vals) < 13:
                    return None
                return (vals[0] / vals[12]) - 1.0
            return vals[0] / 100.0
        except Exception as exc:  # noqa: BLE001
            logger.warning("FRED failed for %s: %s", series_id, exc)
            return None

    @timed
    def _fetch_usd_cop(self) -> float | None:
        # Use yfinance first — handles MultiIndex and User-Agent automatically.
        try:
            df = self._fetch_prices_yfinance("USDCOP=X", None, None)
            return float(df["close"].dropna().iloc[-1])
        except Exception as exc:  # noqa: BLE001
            logger.warning("USD/COP yfinance failed: %s", exc)
        # Fallback to raw Yahoo (now also has User-Agent header).
        try:
            df = self._fetch_prices_yahoo("USDCOP=X", None, None)
            return float(df["close"].dropna().iloc[-1])
        except Exception as exc:  # noqa: BLE001
            logger.warning("USD/COP raw yahoo failed: %s", exc)
        return None

    def get_macro_snapshot(self) -> dict[str, float]:
        global _macro_cache, _macro_cache_ts  # noqa: PLW0603
        if _macro_cache is not None and (time.time() - _macro_cache_ts) < _MACRO_CACHE_TTL:
            return dict(_macro_cache)

        rf = self._fetch_fred_latest("DGS10")
        inflation = self._fetch_fred_latest("CPIAUCSL", yoy=True)
        usd_cop = self._fetch_usd_cop()

        if rf is None:
            rf = 0.045
        if inflation is None:
            inflation = 0.04
        if usd_cop is None:
            usd_cop = 4000.0

        result: dict[str, float] = {
            "risk_free_rate_annual": float(rf),
            "inflation_yoy": float(inflation),
            "usd_cop": float(usd_cop),
        }
        _macro_cache = result
        _macro_cache_ts = time.time()
        return dict(result)


class TechnicalIndicators:
    def __init__(self, settings: Settings):
        self.settings = settings

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        close = out["close"]
        high = out["high"]
        low = out["low"]

        out["sma"] = close.rolling(self.settings.sma_window).mean()
        out["ema"] = close.ewm(span=self.settings.ema_window, adjust=False).mean()

        delta = close.diff()
        gain = delta.clip(lower=0).rolling(self.settings.rsi_window).mean()
        loss = (-delta.clip(upper=0)).rolling(self.settings.rsi_window).mean()
        rs = gain / loss.replace(0, np.nan)
        out["rsi"] = 100 - (100 / (1 + rs))

        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        out["macd"] = ema12 - ema26
        out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()
        out["macd_hist"] = out["macd"] - out["macd_signal"]

        mid = close.rolling(self.settings.bb_window).mean()
        sig = close.rolling(self.settings.bb_window).std()
        out["bb_mid"] = mid
        out["bb_upper"] = mid + self.settings.bb_std * sig
        out["bb_lower"] = mid - self.settings.bb_std * sig

        low_min = low.rolling(self.settings.stoch_window).min()
        high_max = high.rolling(self.settings.stoch_window).max()
        out["stoch_k"] = 100 * (close - low_min) / (high_max - low_min).replace(0, np.nan)
        out["stoch_d"] = out["stoch_k"].rolling(3).mean()
        return out


@dataclass
class RiskCalculator:
    settings: Settings
    data_service: DataService

    def __post_init__(self) -> None:
        self.indicator_engine = TechnicalIndicators(self.settings)

    @staticmethod
    def _classify_beta(beta: float) -> str:
        if beta > 1.2:
            return "agresivo"
        if beta < 0.8:
            return "defensivo"
        return "neutro"

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

        s = out["simple_return"]
        jb_stat, jb_p = stats.jarque_bera(s)
        sh_sample = s.sample(min(5000, len(s)), random_state=42)
        sh_stat, sh_p = stats.shapiro(sh_sample)

        stats_payload = {
            "mean": float(s.mean()),
            "std": float(s.std(ddof=1)),
            "skewness": float(s.skew()),
            "kurtosis": float(s.kurtosis()),
            "jarque_bera_stat": float(jb_stat),
            "jarque_bera_pvalue": float(jb_p),
            "shapiro_stat": float(sh_stat),
            "shapiro_pvalue": float(sh_p),
        }

        return {
            "ticker": ticker,
            "points": out[["date", "simple_return", "log_return"]].to_dict(orient="records"),
            "stats": stats_payload,
        }

    @timed
    def indicators(self, ticker: str, start: str | None = None, end: str | None = None) -> dict:
        df = self.data_service.fetch_prices_df(ticker=ticker, start=start, end=end)
        out = self.indicator_engine.compute(df)
        cols = [
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
        return {"ticker": ticker, "points": out[cols].replace({np.nan: None}).to_dict(orient="records")}

    @timed
    def var_cvar(self, tickers: list[str], weights: list[float], confidence: float) -> dict:
        rets = self.data_service.fetch_close_returns_matrix(tickers)
        w = np.array(weights)
        p = rets.values @ w
        alpha = 1.0 - confidence

        mu = float(np.mean(p))
        sigma = float(np.std(p, ddof=1))
        z = stats.norm.ppf(alpha)

        var_param = float(max(0.0, -(mu + z * sigma)))
        var_hist = float(max(0.0, -np.quantile(p, alpha)))

        tail_thr = np.quantile(p, alpha)
        tail = p[p <= tail_thr]
        cvar = float(max(0.0, -tail.mean())) if len(tail) else var_hist

        mc = np.random.normal(loc=mu, scale=sigma, size=self.settings.monte_carlo_sims)
        var_mc = float(max(0.0, -np.quantile(mc, alpha)))

        ann = np.sqrt(self.settings.trading_days)
        return {
            "confidence": confidence,
            "var_parametric_daily": var_param,
            "var_parametric_annualized": float(var_param * ann),
            "var_historical_daily": var_hist,
            "var_historical_annualized": float(var_hist * ann),
            "var_monte_carlo_daily": var_mc,
            "var_monte_carlo_annualized": float(var_mc * ann),
            "cvar_historical_daily": cvar,
            "monte_carlo_simulations": int(self.settings.monte_carlo_sims),
        }

    @timed
    def capm(self, tickers: list[str] | None = None, benchmark: str | None = None) -> dict:
        assets = tickers or [t for t in self.settings.default_tickers if t != self.settings.default_benchmark]
        bench = benchmark or self.settings.default_benchmark
        universe = list(dict.fromkeys(assets + [bench]))

        rets = self.data_service.fetch_close_returns_matrix(universe)
        market = rets[bench]
        rf = self.data_service.get_macro_snapshot()["risk_free_rate_annual"]
        m_ann = float(market.mean() * self.settings.trading_days)

        rows = []
        for t in assets:
            if t not in rets.columns:
                continue
            s = rets[t]
            cov = np.cov(s.values, market.values, ddof=1)[0, 1]
            var_m = np.var(market.values, ddof=1)
            beta = float(cov / var_m) if var_m > 0 else 0.0
            ann_ret = float(s.mean() * self.settings.trading_days)
            expected = float(rf + beta * (m_ann - rf))
            rows.append(
                {
                    "ticker": t,
                    "beta": beta,
                    "expected_return_capm": expected,
                    "annualized_asset_return": ann_ret,
                    "annualized_market_return": m_ann,
                    "classification": self._classify_beta(beta),
                }
            )

        return {"benchmark": bench, "risk_free_rate": float(rf), "assets": rows}

    @timed
    def frontier(self, tickers: list[str], n_portfolios: int) -> dict:
        rets = self.data_service.fetch_close_returns_matrix(tickers)
        mu = rets.mean().values * self.settings.trading_days
        cov = rets.cov().values * self.settings.trading_days
        rf = self.data_service.get_macro_snapshot()["risk_free_rate_annual"]

        n = len(tickers)
        sims = []
        for _ in range(n_portfolios):
            w = np.random.random(n)
            w = w / w.sum()
            r = float(np.dot(w, mu))
            v = float(np.sqrt(np.dot(w.T, np.dot(cov, w))))
            s = float((r - rf) / v) if v > 0 else 0.0
            sims.append((r, v, s, w))

        points = [{"expected_return": r, "volatility": v, "sharpe": s} for r, v, s, _ in sims]

        sims_sorted = sorted(sims, key=lambda x: x[0])
        efficient = []
        min_vol = float("inf")
        for r, v, s, w in reversed(sims_sorted):
            if v < min_vol:
                efficient.append((r, v, s, w))
                min_vol = v
        efficient = list(reversed(efficient))

        min_var = min(sims, key=lambda x: x[1])
        max_sharpe = max(sims, key=lambda x: x[2])

        def build_portfolio(e: tuple[float, float, float, np.ndarray]) -> dict:
            r, v, s, w = e
            return {
                "expected_return": float(r),
                "volatility": float(v),
                "sharpe": float(s),
                "weights": {t: float(ww) for t, ww in zip(tickers, w)},
            }

        return {
            "points": points,
            "efficient_frontier": [{"expected_return": r, "volatility": v, "sharpe": s} for r, v, s, _ in efficient],
            "min_variance": build_portfolio(min_var),
            "max_sharpe": build_portfolio(max_sharpe),
        }

    @timed
    def alerts(
        self,
        tickers: list[str] | None = None,
        rsi_overbought: float = 70.0,
        rsi_oversold: float = 30.0,
        stoch_overbought: float = 80.0,
        stoch_oversold: float = 20.0,
        short_ma_window: int = 50,
        long_ma_window: int = 200,
    ) -> dict:
        universe = tickers or [t for t in self.settings.default_tickers if t != self.settings.default_benchmark]
        out = []

        if short_ma_window >= long_ma_window:
            raise ValueError("short_ma_window debe ser menor que long_ma_window")

        for t in universe:
            base_df = self.data_service.fetch_prices_df(t)
            ind_df = self.indicator_engine.compute(base_df)
            ind_df["short_ma"] = ind_df["close"].rolling(short_ma_window).mean()
            ind_df["long_ma"] = ind_df["close"].rolling(long_ma_window).mean()
            pts = ind_df.dropna(subset=["rsi", "macd", "macd_signal", "stoch_k", "stoch_d", "short_ma", "long_ma"]).copy()
            if len(pts) < 3:
                continue

            prev = pts.iloc[-2]
            last = pts.iloc[-1]
            reasons = []

            if prev["macd"] <= prev["macd_signal"] and last["macd"] > last["macd_signal"]:
                reasons.append("Cruce alcista MACD")
            if prev["macd"] >= prev["macd_signal"] and last["macd"] < last["macd_signal"]:
                reasons.append("Cruce bajista MACD")

            if last["rsi"] > rsi_overbought:
                reasons.append(f"RSI en sobrecompra (> {rsi_overbought:.1f})")
            elif last["rsi"] < rsi_oversold:
                reasons.append(f"RSI en sobreventa (< {rsi_oversold:.1f})")

            if last["close"] >= last["bb_upper"]:
                reasons.append("Precio tocando o por encima de banda superior")
            if last["close"] <= last["bb_lower"]:
                reasons.append("Precio tocando o por debajo de banda inferior")

            if prev["short_ma"] <= prev["long_ma"] and last["short_ma"] > last["long_ma"]:
                reasons.append("Golden cross de medias moviles")
            if prev["short_ma"] >= prev["long_ma"] and last["short_ma"] < last["long_ma"]:
                reasons.append("Death cross de medias moviles")

            if prev["stoch_k"] <= prev["stoch_d"] and last["stoch_k"] > last["stoch_d"] and last["stoch_k"] <= stoch_oversold:
                reasons.append(f"Cruce alcista estocastico en sobreventa (<= {stoch_oversold:.1f})")
            if prev["stoch_k"] >= prev["stoch_d"] and last["stoch_k"] < last["stoch_d"] and last["stoch_k"] >= stoch_overbought:
                reasons.append(f"Cruce bajista estocastico en sobrecompra (>= {stoch_overbought:.1f})")

            signal = "neutral"
            if any("alcista" in r or "sobreventa" in r or "debajo" in r for r in reasons):
                signal = "buy"
            if any("bajista" in r or "sobrecompra" in r or "encima" in r for r in reasons):
                signal = "sell" if signal == "neutral" else "mixed"

            out.append({"ticker": t, "signal": signal, "reasons": reasons or ["Sin senal activa"]})

        return {"alerts": out}

    @timed
    def macro(self) -> dict:
        return self.data_service.get_macro_snapshot()

    @timed
    def volatility_models(
        self,
        ticker: str,
        start: str | None = None,
        end: str | None = None,
        forecast_steps: int = 20,
    ) -> dict:
        df = self.data_service.fetch_prices_df(ticker=ticker, start=start, end=end)
        r = np.log(df["close"] / df["close"].shift(1)).dropna() * 100.0

        models = {
            "ARCH(1)": arch_model(r, vol="ARCH", p=1, q=0, dist="normal"),
            "GARCH(1,1)": arch_model(r, vol="GARCH", p=1, q=1, dist="normal"),
            "EGARCH(1,1)": arch_model(r, vol="EGARCH", p=1, q=1, dist="normal"),
        }

        fitted = {}
        rows = []
        for name, m in models.items():
            fit = m.fit(disp="off")
            fitted[name] = fit
            rows.append(
                {
                    "model_name": name,
                    "log_likelihood": float(fit.loglikelihood),
                    "aic": float(fit.aic),
                    "bic": float(fit.bic),
                }
            )

        best = min(rows, key=lambda x: x["aic"])
        best_fit = fitted[best["model_name"]]
        try:
            forecast = best_fit.forecast(horizon=forecast_steps)
        except ValueError as exc:
            msg = str(exc).lower()
            # EGARCH and some specs do not support analytic forecasts for h>1.
            if "analytic forecasts not available" in msg and forecast_steps > 1:
                forecast = best_fit.forecast(horizon=forecast_steps, method="simulation", simulations=5000)
            else:
                raise
        forecast_variance = forecast.variance.iloc[-1].values
        vol_path = [float(np.sqrt(v) / 100.0) for v in forecast_variance]
        vol_next = vol_path[0]

        resid = pd.Series(best_fit.std_resid).dropna()
        jb_stat, jb_p = stats.jarque_bera(resid.values)

        aligned_dates = pd.to_datetime(df["date"].iloc[1:]).dt.date.reset_index(drop=True)
        cond_vals = np.asarray(best_fit.conditional_volatility, dtype=float)
        cond_vol = pd.Series(cond_vals, index=aligned_dates).dropna()
        resid_series = pd.Series(resid.values, index=aligned_dates.iloc[-len(resid) :])

        return {
            "ticker": ticker,
            "models": rows,
            "best_model": best["model_name"],
            "forecast_next_day_volatility": vol_next,
            "forecast_path": [{"step": i + 1, "forecast_volatility": v} for i, v in enumerate(vol_path)],
            "residuals": [{"date": d, "std_residual": float(v)} for d, v in resid_series.items()],
            "conditional_volatility": [{"date": d, "conditional_volatility": float(v / 100.0)} for d, v in cond_vol.items()],
            "residuals_jarque_bera_stat": float(jb_stat),
            "residuals_jarque_bera_pvalue": float(jb_p),
        }

    def sources(self) -> dict:
        return self.data_service.sources_status()

    async def prices_async(self, ticker: str, start: str | None = None, end: str | None = None) -> dict:
        return await asyncio.to_thread(self.prices, ticker, start, end)

    async def returns_async(self, ticker: str, start: str | None = None, end: str | None = None) -> dict:
        return await asyncio.to_thread(self.returns, ticker, start, end)

    async def indicators_async(self, ticker: str, start: str | None = None, end: str | None = None) -> dict:
        return await asyncio.to_thread(self.indicators, ticker, start, end)

    async def var_cvar_async(self, tickers: list[str], weights: list[float], confidence: float) -> dict:
        return await asyncio.to_thread(self.var_cvar, tickers, weights, confidence)

    async def capm_async(self, tickers: list[str] | None = None, benchmark: str | None = None) -> dict:
        return await asyncio.to_thread(self.capm, tickers, benchmark)

    async def frontier_async(self, tickers: list[str], n_portfolios: int) -> dict:
        return await asyncio.to_thread(self.frontier, tickers, n_portfolios)

    async def alerts_async(
        self,
        tickers: list[str] | None = None,
        rsi_overbought: float = 70.0,
        rsi_oversold: float = 30.0,
        stoch_overbought: float = 80.0,
        stoch_oversold: float = 20.0,
        short_ma_window: int = 50,
        long_ma_window: int = 200,
    ) -> dict:
        return await asyncio.to_thread(
            self.alerts,
            tickers,
            rsi_overbought,
            rsi_oversold,
            stoch_overbought,
            stoch_oversold,
            short_ma_window,
            long_ma_window,
        )

    async def macro_async(self) -> dict:
        return await asyncio.to_thread(self.macro)

    async def volatility_models_async(
        self,
        ticker: str,
        start: str | None = None,
        end: str | None = None,
        forecast_steps: int = 20,
    ) -> dict:
        return await asyncio.to_thread(self.volatility_models, ticker, start, end, forecast_steps)

    async def sources_async(self) -> dict:
        return await asyncio.to_thread(self.sources)
