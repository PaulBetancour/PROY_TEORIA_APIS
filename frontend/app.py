from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import html

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from requests import HTTPError
from plotly.subplots import make_subplots
from scipy import stats

DEFAULT_TICKERS = ["NVDA", "CIB", "EC", "KO", "SPY"]


@dataclass
class ApiClient:
    base_url: str

    def _url(self, path: str) -> str:
        path = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url.rstrip('/')}{path}"

    def get(self, path: str, params: dict | None = None) -> dict:
        response = requests.get(self._url(path), params=params or {}, timeout=60)
        self._raise_for_status_with_detail(response)
        return response.json()

    def post(self, path: str, payload: dict) -> dict:
        response = requests.post(self._url(path), json=payload, timeout=60)
        self._raise_for_status_with_detail(response)
        return response.json()

    @staticmethod
    def _raise_for_status_with_detail(response: requests.Response) -> None:
        try:
            response.raise_for_status()
        except HTTPError as exc:
            detail = None
            try:
                payload = response.json()
                detail = payload.get("detail") if isinstance(payload, dict) else None
            except ValueError:
                detail = response.text.strip() or None
            if detail:
                raise HTTPError(f"{exc} - {detail}", response=response) from exc
            raise


@st.cache_data(show_spinner=False)
def api_get(base_url: str, path: str, params: dict | None = None) -> dict:
    return ApiClient(base_url).get(path, params=params)


@st.cache_data(show_spinner=False)
def api_post(base_url: str, path: str, payload: dict) -> dict:
    return ApiClient(base_url).post(path, payload=payload)


def api_get_live(base_url: str, path: str, params: dict | None = None) -> dict:
    return ApiClient(base_url).get(path, params=params)


@st.cache_data(show_spinner=False)
def get_prices(base_url: str, ticker: str, start: date, end: date) -> pd.DataFrame:
    data = api_get(
        base_url,
        f"/precios/{ticker}",
        params={"start_date": start.isoformat(), "end_date": end.isoformat()},
    )
    df = pd.DataFrame(data["points"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def get_returns(base_url: str, ticker: str, start: date, end: date) -> pd.DataFrame:
    data = api_get(
        base_url,
        f"/rendimientos/{ticker}",
        params={"start_date": start.isoformat(), "end_date": end.isoformat()},
    )
    df = pd.DataFrame(data["points"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def compute_indicators(
    df: pd.DataFrame,
    sma_window: int,
    ema_window: int,
    rsi_window: int,
    bb_window: int,
    bb_std: float,
    stoch_window: int,
) -> pd.DataFrame:
    out = df.copy()
    close = out["close"]
    high = out["high"]
    low = out["low"]

    out["sma"] = close.rolling(sma_window).mean()
    out["ema"] = close.ewm(span=ema_window, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(rsi_window).mean()
    loss = (-delta.clip(upper=0)).rolling(rsi_window).mean()
    rs = gain / loss.replace(0, np.nan)
    out["rsi"] = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]

    mid = close.rolling(bb_window).mean()
    sig = close.rolling(bb_window).std()
    out["bb_mid"] = mid
    out["bb_upper"] = mid + bb_std * sig
    out["bb_lower"] = mid - bb_std * sig

    low_min = low.rolling(stoch_window).min()
    high_max = high.rolling(stoch_window).max()
    out["stoch_k"] = 100 * (close - low_min) / (high_max - low_min).replace(0, np.nan)
    out["stoch_d"] = out["stoch_k"].rolling(3).mean()

    return out


def returns_matrix(base_url: str, tickers: list[str], start: date, end: date) -> pd.DataFrame:
    series = []
    for t in tickers:
        df = get_returns(base_url, t, start, end)
        s = df.set_index("date")["simple_return"].rename(t)
        series.append(s)
    out = pd.concat(series, axis=1).dropna(how="any")
    return out


def one_paragraph(text: str) -> None:
    st.markdown(f"<div style='font-size: 0.97rem; text-align: justify;'>{text}</div>", unsafe_allow_html=True)


def inject_custom_styles() -> None:
    st.markdown(
        """
        <style>
        .analysis-title {
            font-size: 1.14rem;
            font-weight: 700;
            color: #0b3c5d;
            margin: 0.35rem 0 0.45rem 0;
        }
        .analysis-table {
            width: 100%;
            border-collapse: collapse;
            border: 1px solid #dbe7f3;
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 0.7rem;
            font-size: 1.05rem;
            color: #102a43;
            box-shadow: 0 2px 8px rgba(16, 42, 67, 0.06);
        }
        .analysis-table th {
            background: linear-gradient(90deg, #e6f2ff, #f4f9ff);
            color: #0b3c5d;
            font-weight: 700;
            text-align: left;
            padding: 12px;
            border-bottom: 1px solid #dbe7f3;
        }
        .analysis-table td {
            padding: 11px 12px;
            border-bottom: 1px solid #eef3f9;
            vertical-align: top;
            line-height: 1.45;
        }
        .analysis-table tr:nth-child(even) td {
            background: #f9fcff;
        }
        .analysis-table tr:last-child td {
            border-bottom: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_analysis_table(title: str, rows: list[tuple[str, str]]) -> None:
    rows_html = "".join(
        f"<tr><td><strong>{html.escape(label)}</strong></td><td>{html.escape(value)}</td></tr>"
        for label, value in rows
    )
    st.markdown(
        f"""
        <div class='analysis-title'>{html.escape(title)}</div>
        <table class='analysis-table'>
            <thead>
                <tr>
                    <th style='width: 28%;'>Aspecto</th>
                    <th>Interpretacion</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="Proyecto Teoria de Riesgo", page_icon="📈", layout="wide")
    inject_custom_styles()

    st.title("Proyecto Teoria de Riesgo - Dashboard Analitico")
    st.caption("Implementacion completa en Python con backend FastAPI y visualizacion Streamlit")

    with st.sidebar:
        st.subheader("Conexion")
        base_url = st.text_input("URL backend", value="http://127.0.0.1:8000")

        st.subheader("Activos")
        tickers_text = st.text_input("Tickers (separados por coma)", value=", ".join(DEFAULT_TICKERS))
        tickers = [x.strip().upper() for x in tickers_text.split(",") if x.strip()]
        if not tickers:
            st.error("Debes ingresar al menos un ticker")
            st.stop()
        if len(set(tickers)) != len(tickers):
            st.error("Los tickers deben ser unicos. Elimina duplicados para continuar.")
            st.stop()

        benchmark = st.selectbox("Benchmark", options=tickers, index=tickers.index("SPY") if "SPY" in tickers else 0)

        today = date.today()
        start_default = today - timedelta(days=365 * 5)
        start_date, end_date = st.date_input("Rango de fechas", value=(start_default, today), min_value=date(2000, 1, 1), max_value=today)

        if start_date >= end_date:
            st.error("La fecha inicial debe ser menor a la final")
            st.stop()

        st.subheader("Pesos para portafolio")
        n = len(tickers)
        base_weight = 1.0 / n
        weights = []
        for t in tickers:
            weights.append(st.number_input(f"Peso {t}", min_value=0.0, max_value=1.0, value=base_weight, step=0.01))

        w_sum = float(np.sum(weights))
        if w_sum <= 0:
            st.error("La suma de pesos debe ser positiva")
            st.stop()
        weights = [w / w_sum for w in weights]

    tabs = st.tabs([
        "M1 Tecnico",
        "M2 Rendimientos",
        "M3 ARCH/GARCH",
        "M4 CAPM",
        "M5 VaR/CVaR",
        "M6 Markowitz",
        "M7 Senales",
        "M8 Macro/Benchmark",
    ])

    try:
        api_get(base_url, "/health")
    except Exception as exc:  # noqa: BLE001
        st.error(f"No se pudo conectar al backend: {exc}")
        st.stop()

    with tabs[0]:
        st.subheader("Modulo 1 - Analisis tecnico")
        st.latex(r"SMA_t=\frac{1}{n}\sum_{i=0}^{n-1}P_{t-i},\quad EMA_t=\alpha P_t+(1-\alpha)EMA_{t-1}")
        st.latex(r"RSI=100-\frac{100}{1+RS},\quad MACD=EMA_{12}-EMA_{26}")

        rep_asset_m1 = st.selectbox(
            "Activo representativo",
            options=tickers,
            index=tickers.index("NVDA") if "NVDA" in tickers else 0,
            key="rep_asset_m1",
        )

        st.markdown("#### Panel explicativo de indicadores")
        st.info(
            "SMA/EMA: miden tendencia (EMA reacciona mas rapido).\n"
            "\nRSI: momento entre 0 y 100; >70 sugiere sobrecompra y <30 sobreventa.\n"
            "\nMACD: diferencia entre EMA(12) y EMA(26); el cruce con la linea de senal confirma cambios de impulso.\n"
            "\nBandas de Bollinger: media movil con bandas de desviacion estandar para detectar expansion/contraccion de volatilidad.\n"
            "\nEstocastico (%K, %D): compara cierre actual con el rango reciente para identificar zonas extremas y posibles reversiones."
        )

        price_mode = st.radio(
            "Tipo de grafico de precios",
            options=["Velas japonesas", "Linea de cierre"],
            horizontal=True,
        )

        c1, c2, c3 = st.columns(3)
        sma_window = c1.slider("SMA", min_value=5, max_value=200, value=20)
        ema_window = c2.slider("EMA", min_value=5, max_value=200, value=20)
        rsi_window = c3.slider("RSI", min_value=5, max_value=50, value=14)

        c4, c5, c6 = st.columns(3)
        bb_window = c4.slider("Bollinger window", min_value=5, max_value=100, value=20)
        bb_std = c5.slider("Bollinger std", min_value=1.0, max_value=3.5, value=2.0, step=0.1)
        stoch_window = c6.slider("Estocastico", min_value=5, max_value=50, value=14)

        for ticker in [rep_asset_m1]:
            st.markdown(f"### {ticker}")
            df = get_prices(base_url, ticker, start_date, end_date)
            ind = compute_indicators(df, sma_window, ema_window, rsi_window, bb_window, bb_std, stoch_window)

            fig_price = go.Figure()
            if price_mode == "Velas japonesas":
                fig_price.add_trace(
                    go.Candlestick(
                        x=ind["date"],
                        open=ind["open"],
                        high=ind["high"],
                        low=ind["low"],
                        close=ind["close"],
                        name="OHLC",
                    )
                )
            else:
                fig_price.add_trace(go.Scatter(x=ind["date"], y=ind["close"], mode="lines", name="Cierre"))
            fig_price.add_trace(go.Scatter(x=ind["date"], y=ind["sma"], mode="lines", name=f"SMA({sma_window})"))
            fig_price.add_trace(go.Scatter(x=ind["date"], y=ind["ema"], mode="lines", name=f"EMA({ema_window})"))
            fig_price.add_trace(go.Scatter(x=ind["date"], y=ind["bb_upper"], mode="lines", name="BB superior", line=dict(dash="dot")))
            fig_price.add_trace(go.Scatter(x=ind["date"], y=ind["bb_lower"], mode="lines", name="BB inferior", line=dict(dash="dot")))
            fig_price.update_layout(
                height=500,
                xaxis=dict(
                    rangeselector=dict(
                        buttons=[
                            dict(count=1, label="1m", step="month", stepmode="backward"),
                            dict(count=6, label="6m", step="month", stepmode="backward"),
                            dict(count=1, label="1a", step="year", stepmode="backward"),
                            dict(label="Todo", step="all"),
                        ]
                    ),
                    rangeslider=dict(visible=True),
                    type="date",
                ),
            )
            st.plotly_chart(fig_price, use_container_width=True)

            fig_osc = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04, subplot_titles=("RSI", "MACD", "Estocastico"))
            fig_osc.add_trace(go.Scatter(x=ind["date"], y=ind["rsi"], mode="lines", name="RSI"), row=1, col=1)
            fig_osc.add_hline(y=70, line_dash="dash", line_color="red", row=1, col=1)
            fig_osc.add_hline(y=30, line_dash="dash", line_color="green", row=1, col=1)

            fig_osc.add_trace(go.Scatter(x=ind["date"], y=ind["macd"], mode="lines", name="MACD"), row=2, col=1)
            fig_osc.add_trace(go.Scatter(x=ind["date"], y=ind["macd_signal"], mode="lines", name="Signal"), row=2, col=1)
            fig_osc.add_trace(go.Bar(x=ind["date"], y=ind["macd_hist"], name="Hist"), row=2, col=1)

            fig_osc.add_trace(go.Scatter(x=ind["date"], y=ind["stoch_k"], mode="lines", name="%K"), row=3, col=1)
            fig_osc.add_trace(go.Scatter(x=ind["date"], y=ind["stoch_d"], mode="lines", name="%D"), row=3, col=1)
            fig_osc.add_hline(y=80, line_dash="dash", line_color="red", row=3, col=1)
            fig_osc.add_hline(y=20, line_dash="dash", line_color="green", row=3, col=1)
            fig_osc.update_layout(height=700)
            st.plotly_chart(fig_osc, use_container_width=True)

            last = ind.iloc[-1]
            table = pd.DataFrame(
                {
                    "Indicador": ["Precio", "SMA", "EMA", "RSI", "MACD", "Signal", "BB Sup", "BB Inf", "%K", "%D"],
                    "Valor": [
                        last["close"],
                        last["sma"],
                        last["ema"],
                        last["rsi"],
                        last["macd"],
                        last["macd_signal"],
                        last["bb_upper"],
                        last["bb_lower"],
                        last["stoch_k"],
                        last["stoch_d"],
                    ],
                }
            )
            st.dataframe(
                table.style.format({"Valor": "{:.4f}"}).set_properties(
                    **{"font-size": "16px", "color": "#102a43", "background-color": "#f9fcff"}
                ),
                use_container_width=True,
            )

            interpretation = (
                f"Para {ticker}, el precio actual ({last['close']:.2f}) se evalua frente a tendencia y momento: "
                f"si el precio supera SMA/EMA se sugiere sesgo alcista de corto plazo, mientras que RSI={last['rsi']:.2f} "
                "acota zonas de sobrecompra/sobreventa; MACD y su histograma muestran aceleracion o perdida de impulso, "
                "y las Bandas de Bollinger junto al Estocastico permiten confirmar si el movimiento reciente luce extendido o con potencial de reversa."
            )
            trend_label = "alcista" if (last["close"] > last["sma"] and last["close"] > last["ema"]) else "mixta/bajista"
            rsi_label = "sobrecompra" if last["rsi"] > 70 else ("sobreventa" if last["rsi"] < 30 else "neutral")
            stoch_label = "sobrecompra" if last["stoch_k"] > 80 else ("sobreventa" if last["stoch_k"] < 20 else "neutral")
            render_analysis_table(
                "Analisis tecnico automatizado",
                [
                    ("Activo", ticker),
                    ("Precio actual", f"{last['close']:.2f}"),
                    ("Tendencia", f"Precio vs medias: sesgo {trend_label}"),
                    ("Momento", f"RSI={last['rsi']:.2f} ({rsi_label}) y MACD={last['macd']:.4f}"),
                    ("Bandas/Estocastico", f"%K={last['stoch_k']:.2f} ({stoch_label}), revisar extension/reversion"),
                    ("Lectura integrada", interpretation),
                ],
            )
            st.divider()

    with tabs[1]:
        st.subheader("Modulo 2 - Rendimientos")
        st.latex(r"R_t=\frac{P_t-P_{t-1}}{P_{t-1}},\quad r_t=\ln\left(\frac{P_t}{P_{t-1}}\right)")

        rep_asset_m2 = st.selectbox(
            "Activo representativo",
            options=tickers,
            index=tickers.index("NVDA") if "NVDA" in tickers else 0,
            key="rep_asset_m2",
        )

        for ticker in [rep_asset_m2]:
            st.markdown(f"### {ticker}")
            r_df = get_returns(base_url, ticker, start_date, end_date)
            calc_preview = r_df[["date", "simple_return", "log_return"]].dropna().tail(12).copy()
            calc_preview["date"] = calc_preview["date"].dt.date
            st.caption("Muestra de calculo de rendimientos simples y logaritmicos")
            st.dataframe(
                calc_preview.style.format({"simple_return": "{:.5f}", "log_return": "{:.5f}"}).set_properties(
                    **{"font-size": "15px", "color": "#102a43", "background-color": "#f9fcff"}
                ),
                use_container_width=True,
            )

            s_simple = r_df["simple_return"].dropna()
            s_log = r_df["log_return"].dropna()

            def describe(series: pd.Series) -> dict[str, float]:
                mean = float(series.mean())
                std = float(series.std(ddof=1))
                skew = float(series.skew())
                kurt = float(series.kurtosis())
                jb_stat, jb_p = stats.jarque_bera(series)
                sh_stat, sh_p = stats.shapiro(series.sample(min(5000, len(series)), random_state=42))
                return {
                    "media": mean,
                    "desv_est": std,
                    "asimetria": skew,
                    "curtosis": kurt,
                    "jb_stat": float(jb_stat),
                    "jb_pvalue": float(jb_p),
                    "shapiro_stat": float(sh_stat),
                    "shapiro_pvalue": float(sh_p),
                }

            desc_simple = describe(s_simple)
            desc_log = describe(s_log)

            stats_table = pd.DataFrame(
                [
                    {"tipo": "simple", **desc_simple},
                    {"tipo": "log", **desc_log},
                ]
            )
            st.dataframe(
                stats_table.style.format(
                    {
                        "media": "{:.6f}",
                        "desv_est": "{:.6f}",
                        "asimetria": "{:.6f}",
                        "curtosis": "{:.6f}",
                        "jb_stat": "{:.4f}",
                        "jb_pvalue": "{:.4f}",
                        "shapiro_stat": "{:.4f}",
                        "shapiro_pvalue": "{:.4f}",
                    }
                ).set_properties(**{"font-size": "15px", "color": "#102a43", "background-color": "#f9fcff"}),
                use_container_width=True,
            )

            ret_view = st.radio(
                "Serie a visualizar",
                options=["simple_return", "log_return"],
                horizontal=True,
                key=f"ret_view_{ticker}",
            )
            s = r_df[ret_view].dropna()
            mean = float(s.mean())
            std = float(s.std(ddof=1))

            x = np.linspace(s.min(), s.max(), 400)
            normal_pdf = stats.norm.pdf(x, loc=mean, scale=std)
            fig_hist = go.Figure()
            fig_hist.add_trace(go.Histogram(x=s, histnorm="probability density", name="Rendimientos", opacity=0.65, nbinsx=60))
            fig_hist.add_trace(go.Scatter(x=x, y=normal_pdf, mode="lines", name="Normal te") )
            fig_hist.update_layout(height=420)
            st.plotly_chart(fig_hist, use_container_width=True)

            qq_theoretical, qq_sample = stats.probplot(s, dist="norm", fit=False)
            slope, intercept, _ = stats.probplot(s, dist="norm", fit=True)[1]
            qq_line = slope * np.array(qq_theoretical) + intercept
            fig_qq = go.Figure()
            fig_qq.add_trace(go.Scatter(x=qq_theoretical, y=qq_sample, mode="markers", name="Q-Q"))
            fig_qq.add_trace(go.Scatter(x=qq_theoretical, y=qq_line, mode="lines", name="Ajuste"))
            fig_qq.update_layout(height=360, xaxis_title="Cuantiles teoricos", yaxis_title="Cuantiles muestrales")
            st.plotly_chart(fig_qq, use_container_width=True)

            fig_box = go.Figure(go.Box(y=s, name=ticker, boxmean=True))
            fig_box.update_layout(height=280)
            st.plotly_chart(fig_box, use_container_width=True)

            ac_abs = s.abs().autocorr(lag=1)
            leverage = s.corr((s**2).shift(-1))
            kurt = float(s.kurtosis())
            stylized = (
                "colas pesadas" if kurt > 0 else "colas cercanas a normal"
            ) + f", clustering de volatilidad (acf |r| lag1={ac_abs:.3f}) y efecto apalancamiento (corr(r_t, r_t^2+1)={leverage:.3f})."

            test_row = desc_simple if ret_view == "simple_return" else desc_log
            jb_p = test_row["jb_pvalue"]
            sh_p = test_row["shapiro_pvalue"]
            normality_msg = (
                f"Normalidad para {ret_view}: JB p={jb_p:.4f} y Shapiro p={sh_p:.4f}. "
                f"Decision (5%): {'no se rechaza' if (jb_p >= 0.05 and sh_p >= 0.05) else 'se rechaza'} normalidad."
            )
            st.info(normality_msg)

            interp = (
                f"En {ticker}, para la serie {ret_view}, la media es {mean:.5f} y la volatilidad {std:.5f}; "
                f"las pruebas de normalidad (JB p={jb_p:.4f}, Shapiro p={sh_p:.4f}) indican "
                f"{'rechazar' if (jb_p < 0.05 or sh_p < 0.05) else 'no rechazar'} normalidad al 5%, y la evidencia de hechos estilizados sugiere {stylized}"
            )
            render_analysis_table(
                "Analisis estadistico automatizado",
                [
                    ("Activo", ticker),
                    ("Serie analizada", ret_view),
                    ("Media y volatilidad", f"media={mean:.5f}, volatilidad={std:.5f}"),
                    ("Normalidad", f"JB p={jb_p:.4f}, Shapiro p={sh_p:.4f}"),
                    (
                        "Decision 5%",
                        "No se rechaza normalidad" if (jb_p >= 0.05 and sh_p >= 0.05) else "Se rechaza normalidad",
                    ),
                    ("Hechos estilizados", stylized),
                    ("Lectura integrada", interp),
                ],
            )
            st.divider()

    with tabs[2]:
        st.subheader("Modulo 3 - ARCH/GARCH")
        st.latex(r"\sigma_t^2=\omega+\sum_{i=1}^{q}\alpha_i\varepsilon_{t-i}^2+\sum_{j=1}^{p}\beta_j\sigma_{t-j}^2")
        st.info(
            "Justificacion: en series financieras la volatilidad no es constante en el tiempo. "
            "Se observan periodos de alta y baja variabilidad (clustering), por lo que un modelo "
            "de varianza condicional (ARCH/GARCH) describe mejor el riesgo que una varianza fija."
        )
        rep_asset = st.selectbox("Activo representativo", options=tickers, index=tickers.index("NVDA") if "NVDA" in tickers else 0)
        forecast_steps = st.slider("Horizonte pronostico", min_value=5, max_value=60, value=20)

        vol = api_get_live(
            base_url,
            f"/volatilidad/{rep_asset}",
            params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "forecast_steps": forecast_steps},
        )

        if st.checkbox("Mostrar comparativo de volatilidad para todos los activos", value=True):
            comp_rows = []
            for tk in tickers:
                try:
                    vv = api_get_live(
                        base_url,
                        f"/volatilidad/{tk}",
                        params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "forecast_steps": forecast_steps},
                    )
                    cond_vals = [float(x["conditional_volatility"]) for x in vv.get("conditional_volatility", [])]
                    comp_rows.append(
                        {
                            "activo": tk,
                            "mejor_modelo": vv.get("best_model"),
                            "vol_next_day": float(vv.get("forecast_next_day_volatility", np.nan)),
                            "vol_cond_media": float(np.mean(cond_vals)) if cond_vals else np.nan,
                            "vol_cond_std": float(np.std(cond_vals, ddof=1)) if len(cond_vals) > 1 else np.nan,
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    comp_rows.append(
                        {
                            "activo": tk,
                            "mejor_modelo": "error",
                            "vol_next_day": np.nan,
                            "vol_cond_media": np.nan,
                            "vol_cond_std": np.nan,
                            "detalle": str(exc),
                        }
                    )
            comp_df = pd.DataFrame(comp_rows)
            st.dataframe(
                comp_df.style.format(
                    {
                        "vol_next_day": "{:.6f}",
                        "vol_cond_media": "{:.6f}",
                        "vol_cond_std": "{:.6f}",
                    }
                ),
                use_container_width=True,
            )

            plot_df = comp_df.dropna(subset=["vol_next_day", "vol_cond_media"]).copy()
            if not plot_df.empty:
                fig_comp = go.Figure()
                fig_comp.add_trace(
                    go.Bar(
                        x=plot_df["activo"],
                        y=plot_df["vol_next_day"],
                        name="Vol. siguiente dia",
                        text=[f"{v:.4%}" for v in plot_df["vol_next_day"]],
                        textposition="outside",
                    )
                )
                fig_comp.add_trace(
                    go.Bar(
                        x=plot_df["activo"],
                        y=plot_df["vol_cond_media"],
                        name="Vol. condicional media",
                        text=[f"{v:.4%}" for v in plot_df["vol_cond_media"]],
                        textposition="outside",
                    )
                )
                fig_comp.update_layout(
                    barmode="group",
                    height=430,
                    yaxis_title="Volatilidad",
                    yaxis_tickformat=".2%",
                    title="Comparativo de volatilidad por activo",
                )
                st.plotly_chart(fig_comp, use_container_width=True)

        model_table = pd.DataFrame(vol["models"]).sort_values("aic")
        st.dataframe(model_table.style.format({"log_likelihood": "{:.2f}", "aic": "{:.2f}", "bic": "{:.2f}"}), use_container_width=True)

        jb_stat = float(vol["residuals_jarque_bera_stat"])
        jb_pvalue = float(vol["residuals_jarque_bera_pvalue"])
        jb_decision = "No se rechaza normalidad" if jb_pvalue >= 0.05 else "Se rechaza normalidad"
        diag_df = pd.DataFrame(
            [
                {
                    "activo": rep_asset,
                    "mejor_modelo": vol["best_model"],
                    "JB_stat": jb_stat,
                    "JB_pvalue": jb_pvalue,
                    "decision_5pct": jb_decision,
                }
            ]
        )
        st.dataframe(diag_df.style.format({"JB_stat": "{:.4f}", "JB_pvalue": "{:.4f}"}), use_container_width=True)

        res_df = pd.DataFrame(vol.get("residuals", []))
        if not res_df.empty and {"date", "std_residual"}.issubset(res_df.columns):
            res_df["date"] = pd.to_datetime(res_df["date"])

            fig_res = go.Figure()
            fig_res.add_trace(go.Scatter(x=res_df["date"], y=res_df["std_residual"], mode="lines", name="Residuos estandarizados"))
            fig_res.add_hline(y=0, line_dash="dash")
            fig_res.update_layout(height=350)
            st.plotly_chart(fig_res, use_container_width=True)

            res_vals = res_df["std_residual"].dropna().values
            if len(res_vals) > 10:
                x = np.linspace(np.min(res_vals), np.max(res_vals), 350)
                normal_pdf = stats.norm.pdf(x, loc=float(np.mean(res_vals)), scale=float(np.std(res_vals, ddof=1)))
                fig_res_hist = go.Figure()
                fig_res_hist.add_trace(go.Histogram(x=res_vals, histnorm="probability density", nbinsx=50, name="Residuos", opacity=0.65))
                fig_res_hist.add_trace(go.Scatter(x=x, y=normal_pdf, mode="lines", name="Normal te"))
                fig_res_hist.update_layout(height=320, title="Diagnostico: distribucion de residuos estandarizados")
                st.plotly_chart(fig_res_hist, use_container_width=True)
        else:
            st.warning("No se pudieron construir los residuos estandarizados para el rango/activo seleccionado.")

        vol_df = pd.DataFrame(vol.get("conditional_volatility", []))
        if not vol_df.empty and {"date", "conditional_volatility"}.issubset(vol_df.columns):
            vol_df["date"] = pd.to_datetime(vol_df["date"])
            fig_cv = go.Figure()
            fig_cv.add_trace(go.Scatter(x=vol_df["date"], y=vol_df["conditional_volatility"], mode="lines", name="Volatilidad condicional"))
            fig_cv.update_layout(height=350)
            st.plotly_chart(fig_cv, use_container_width=True)
        else:
            st.warning("No hay serie de volatilidad condicional disponible para este escenario.")

        f_df = pd.DataFrame(vol.get("forecast_path", []))
        if not f_df.empty and {"step", "forecast_volatility"}.issubset(f_df.columns):
            fig_fc = go.Figure(go.Bar(x=f_df["step"], y=f_df["forecast_volatility"], name="Pronostico"))
            fig_fc.update_layout(height=300, xaxis_title="Paso (N-step ahead)", yaxis_title="Volatilidad")
            st.plotly_chart(fig_fc, use_container_width=True)
        else:
            st.warning("No se pudo construir el pronostico de volatilidad para los parametros actuales.")

        interp = (
            f"Para {rep_asset}, se estimaron ARCH(1), GARCH(1,1) y EGARCH(1,1), resultando mejor {vol['best_model']} por AIC; "
            f"el test Jarque-Bera sobre residuos estandarizados (p={vol['residuals_jarque_bera_pvalue']:.4f}) "
            "evalua normalidad residual, mientras la volatilidad condicional y su pronostico por horizonte muestran persistencia temporal, "
            "justificando el uso de modelos condicionales frente a una varianza constante."
        )
        render_analysis_table(
            "Interpretacion del modelo ARCH/GARCH",
            [
                ("Activo", rep_asset),
                ("Modelo ganador", f"{vol['best_model']} (criterio AIC)"),
                ("Normalidad de residuos", f"Jarque-Bera p={vol['residuals_jarque_bera_pvalue']:.4f}"),
                ("Volatilidad condicional", "Se observa dinamica temporal y clustering de volatilidad."),
                ("Pronostico", f"Horizonte evaluado: {forecast_steps} pasos hacia adelante."),
                ("Lectura integrada", interp),
            ],
        )

    with tabs[3]:
        st.subheader("Modulo 4 - CAPM y Beta")
        st.latex(r"E[R_i]=R_f+\beta_i(E[R_m]-R_f),\quad \beta_i=\frac{\mathrm{Cov}(R_i,R_m)}{\mathrm{Var}(R_m)}")

        assets_capm = [t for t in tickers if t != benchmark]
        capm = api_get(base_url, "/capm", params={"tickers": ",".join(assets_capm), "benchmark": benchmark})
        macro = api_get(base_url, "/macro")

        rf_capm = float(capm["risk_free_rate"])
        rf_macro = float(macro["risk_free_rate_annual"])
        rf_gap = abs(rf_capm - rf_macro)
        c1, c2, c3 = st.columns(3)
        c1.metric("R_f CAPM", f"{rf_capm:.4f}")
        c2.metric("R_f API macro", f"{rf_macro:.4f}")
        c3.metric("Diferencia |CAPM-macro|", f"{rf_gap:.6f}")
        if rf_gap < 1e-9:
            st.success("CAPM usa automaticamente la tasa libre de riesgo obtenida desde /macro.")
        else:
            st.warning("La tasa CAPM difiere de /macro; revisa consistencia en backend.")

        capm_table = pd.DataFrame(capm["assets"])
        if not capm_table.empty and "classification" in capm_table.columns:
            class_count = capm_table["classification"].value_counts()
            c4, c5, c6 = st.columns(3)
            c4.metric("Activos agresivos", int(class_count.get("agresivo", 0)))
            c5.metric("Activos neutros", int(class_count.get("neutro", 0)))
            c6.metric("Activos defensivos", int(class_count.get("defensivo", 0)))

        st.dataframe(
            capm_table.style.format(
                {
                    "beta": "{:.4f}",
                    "expected_return_capm": "{:.4f}",
                    "annualized_asset_return": "{:.4f}",
                    "annualized_market_return": "{:.4f}",
                }
            ),
            use_container_width=True,
        )

        rm = get_returns(base_url, benchmark, start_date, end_date).set_index("date")["simple_return"]
        for asset in assets_capm:
            ra = get_returns(base_url, asset, start_date, end_date).set_index("date")["simple_return"]
            joined = pd.concat([ra.rename("asset"), rm.rename("market")], axis=1).dropna()
            if joined.empty:
                continue
            slope, intercept, _, _, _ = stats.linregress(joined["market"], joined["asset"])
            x = np.linspace(joined["market"].min(), joined["market"].max(), 100)
            y = intercept + slope * x
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=joined["market"], y=joined["asset"], mode="markers", name=asset, opacity=0.5))
            fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name="Regresion"))
            fig.update_layout(height=320, xaxis_title=f"Rendimiento {benchmark}", yaxis_title=f"Rendimiento {asset}")
            st.plotly_chart(fig, use_container_width=True)

        interp = (
            f"Con tasa libre de riesgo anual automatica de {capm['risk_free_rate']:.4f}, el CAPM estima retorno esperado segun beta para cada activo; "
            "los activos con beta alta concentran mayor riesgo sistematico (no diversificable), mientras que el riesgo no sistematico "
            "puede reducirse combinando activos con distinta exposicion al mercado, como se observa en la dispersion frente al benchmark y su recta de regresion."
        )
        render_analysis_table(
            "Interpretacion CAPM y riesgo sistematico",
            [
                ("Benchmark", benchmark),
                ("Tasa libre de riesgo", f"CAPM={rf_capm:.4f}, Macro API={rf_macro:.4f}"),
                ("Consistencia de tasa", "Consistente" if rf_gap < 1e-9 else "Revisar diferencia CAPM vs macro"),
                ("Lectura de beta", "Beta alta implica mayor sensibilidad al mercado (riesgo sistematico)."),
                ("Diversificacion", "El riesgo no sistematico se mitiga combinando activos."),
                ("Lectura integrada", interp),
            ],
        )

    with tabs[4]:
        st.subheader("Modulo 5 - VaR y CVaR")
        st.latex(r"VaR_\alpha=-Q_\alpha(R_p),\quad CVaR_\alpha=-E[R_p\mid R_p\le Q_\alpha(R_p)]")

        try:
            payload = {"tickers": tickers, "weights": weights, "confidence": 0.95}
            var95 = api_post(base_url, "/var", payload)
            payload99 = {"tickers": tickers, "weights": weights, "confidence": 0.99}
            var99 = api_post(base_url, "/var", payload99)
        except Exception as exc:  # noqa: BLE001
            st.error(f"No se pudo calcular VaR/CVaR: {exc}")
            st.info("Revisa que los tickers sean unicos y que el backend tenga datos disponibles para todos los activos.")
            var95 = None
            var99 = None

        if var95 is not None and var99 is not None:
            sims = int(var95.get("monte_carlo_simulations", 0))
            c1, c2 = st.columns(2)
            c1.metric("Simulaciones Montecarlo", sims)
            c2.metric("Cumple minimo requerido", "SI" if sims >= 10000 else "NO")
            if sims < 10000:
                st.warning("El modulo requiere al menos 10,000 simulaciones Montecarlo.")

            summary = pd.DataFrame(
                {
                    "Metodo": ["Parametrico", "Historico", "Montecarlo"],
                    "VaR 95 diario": [var95["var_parametric_daily"], var95["var_historical_daily"], var95["var_monte_carlo_daily"]],
                    "VaR 95 anual": [var95["var_parametric_annualized"], var95["var_historical_annualized"], var95["var_monte_carlo_annualized"]],
                    "VaR 99 diario": [var99["var_parametric_daily"], var99["var_historical_daily"], var99["var_monte_carlo_daily"]],
                    "VaR 99 anual": [var99["var_parametric_annualized"], var99["var_historical_annualized"], var99["var_monte_carlo_annualized"]],
                    "CVaR 95 diario": [np.nan, var95["cvar_historical_daily"], np.nan],
                    "CVaR 99 diario": [np.nan, var99["cvar_historical_daily"], np.nan],
                }
            )
            numeric_cols = [c for c in summary.columns if c != "Metodo"]
            fmt_summary = {c: "{:.5f}" for c in numeric_cols}
            st.dataframe(summary.style.format(fmt_summary), use_container_width=True)

            interpret = pd.DataFrame(
                {
                    "Metodo": ["Parametrico", "Historico", "Montecarlo", "CVaR (Expected Shortfall)"],
                    "Lectura": [
                        "Asume distribucion normal y usa media/desv. estandar.",
                        "No impone forma paramétrica; usa cuantiles observados.",
                        f"Simula escenarios aleatorios (n={sims}) con media y volatilidad estimada.",
                        "Mide severidad esperada de perdidas extremas una vez superado el VaR.",
                    ],
                }
            )
            st.dataframe(interpret, use_container_width=True)

            ret_mat = returns_matrix(base_url, tickers, start_date, end_date)
            w = np.array(weights)
            rp = pd.Series(ret_mat.values @ w, index=ret_mat.index, name="portfolio")

            fig = go.Figure()
            fig.add_trace(go.Histogram(x=rp, nbinsx=80, histnorm="probability density", name="Portafolio", opacity=0.7))
            fig.add_vline(x=-var95["var_historical_daily"], line_dash="dash", line_color="orange", annotation_text="VaR95 hist")
            fig.add_vline(x=-var99["var_historical_daily"], line_dash="dash", line_color="red", annotation_text="VaR99 hist")
            fig.add_vline(x=-var95["cvar_historical_daily"], line_dash="dot", line_color="black", annotation_text="CVaR95")
            fig.add_vline(x=-var99["cvar_historical_daily"], line_dash="dot", line_color="purple", annotation_text="CVaR99")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

            exceed = (rp < -var95["var_historical_daily"]).astype(int)
            x = int(exceed.sum())
            n = int(len(exceed))
            p = 0.05
            phat = x / n if n > 0 else 0.0
            if x in {0, n}:
                kupiec_p = np.nan
            else:
                lr_uc = -2 * (
                    ((n - x) * np.log(1 - p) + x * np.log(p))
                    - ((n - x) * np.log(1 - phat) + x * np.log(phat))
                )
                kupiec_p = 1 - stats.chi2.cdf(lr_uc, df=1)
            interp = (
                f"Con los pesos normalizados del portafolio, el VaR y CVaR muestran la perdida potencial diaria y anual bajo metodos parametrico, historico y Montecarlo (n={sims} simulaciones); "
                f"en 95% el CVaR={var95['cvar_historical_daily']:.5f} y en 99% el CVaR={var99['cvar_historical_daily']:.5f} cuantifican la severidad promedio en cola y complementan al VaR, "
                "mientras que el test de Kupiec (opcional) evalua si la frecuencia de excepciones observada es consistente con el nivel de confianza."
            )
            render_analysis_table(
                "Interpretacion de riesgo VaR/CVaR",
                [
                    ("Simulaciones", f"Montecarlo n={sims}"),
                    ("VaR historico diario 95%", f"{var95['var_historical_daily']:.5f}"),
                    ("VaR historico diario 99%", f"{var99['var_historical_daily']:.5f}"),
                    ("CVaR diario 95%", f"{var95['cvar_historical_daily']:.5f}"),
                    ("CVaR diario 99%", f"{var99['cvar_historical_daily']:.5f}"),
                    ("Backtesting Kupiec", f"Excepciones={x}/{n}, p-value={kupiec_p:.4f}"),
                    ("Lectura integrada", interp),
                ],
            )

    with tabs[5]:
        st.subheader("Modulo 6 - Markowitz")
        st.latex(r"\min_w\ w^T\Sigma w\ \text{s.a.}\ \sum_i w_i=1,\quad Sharpe=\frac{E[R_p]-R_f}{\sigma_p}")

        n_port = st.slider("Numero de portafolios simulados", min_value=10000, max_value=40000, value=10000, step=1000)
        frontier = api_post(base_url, "/frontera-eficiente", payload={"tickers": tickers, "n_portfolios": n_port})

        ret_mat = returns_matrix(base_url, tickers, start_date, end_date)
        corr = ret_mat.corr()
        fig_corr = go.Figure(data=go.Heatmap(z=corr.values, x=corr.columns, y=corr.index, colorscale="RdBu", zmin=-1, zmax=1))
        fig_corr.update_layout(height=420)
        st.plotly_chart(fig_corr, use_container_width=True)

        pts = pd.DataFrame(frontier["points"])
        eff = pd.DataFrame(frontier["efficient_frontier"])
        st.caption(f"Portafolios simulados: {len(pts)}")
        fig_front = go.Figure()
        fig_front.add_trace(go.Scatter(x=pts["volatility"], y=pts["expected_return"], mode="markers", marker=dict(color=pts["sharpe"], colorscale="Viridis", size=4), name="Factible"))
        fig_front.add_trace(go.Scatter(x=eff["volatility"], y=eff["expected_return"], mode="lines", line=dict(color="red", width=3), name="Frontera eficiente"))
        mv = frontier["min_variance"]
        ms = frontier["max_sharpe"]
        fig_front.add_trace(go.Scatter(x=[mv["volatility"]], y=[mv["expected_return"]], mode="markers", marker=dict(size=14, color="blue"), name="Min var"))
        fig_front.add_trace(go.Scatter(x=[ms["volatility"]], y=[ms["expected_return"]], mode="markers", marker=dict(size=14, color="gold"), name="Max Sharpe"))
        fig_front.update_layout(height=500, xaxis_title="Volatilidad", yaxis_title="Retorno esperado")
        st.plotly_chart(fig_front, use_container_width=True)

        w_mv = pd.DataFrame([mv["weights"]]).T.reset_index()
        w_mv.columns = ["Ticker", "Peso min var"]
        w_ms = pd.DataFrame([ms["weights"]]).T.reset_index()
        w_ms.columns = ["Ticker", "Peso max sharpe"]
        table_w = w_mv.merge(w_ms, on="Ticker", how="outer")
        table_w["Peso min var (%)"] = table_w["Peso min var"] * 100.0
        table_w["Peso max sharpe (%)"] = table_w["Peso max sharpe"] * 100.0
        st.dataframe(
            table_w.style.format(
                {
                    "Peso min var": "{:.4f}",
                    "Peso max sharpe": "{:.4f}",
                    "Peso min var (%)": "{:.2f}%",
                    "Peso max sharpe (%)": "{:.2f}%",
                }
            ),
            use_container_width=True,
        )

        target = st.number_input("Rendimiento objetivo anual (opcional)", min_value=-1.0, max_value=2.0, value=0.20, step=0.01)
        if not eff.empty:
            idx = (eff["expected_return"] - target).abs().idxmin()
            near = eff.loc[idx]

        interp = (
            "La matriz de correlacion confirma el potencial de diversificacion entre activos, y la simulacion de 10,000+ combinaciones permite identificar "
            "el portafolio de minima varianza (menor riesgo total) y el de maximo Sharpe (mejor retorno por unidad de riesgo); la frontera eficiente resume "
            "las carteras dominantes para decidir segun tolerancia al riesgo u objetivo de retorno."
        )
        render_analysis_table(
            "Interpretacion de frontera eficiente",
            [
                ("Portafolios simulados", f"{len(pts)}"),
                ("Cartera minima varianza", f"Retorno={mv['expected_return']:.4f}, Vol={mv['volatility']:.4f}"),
                ("Cartera maximo Sharpe", f"Retorno={ms['expected_return']:.4f}, Vol={ms['volatility']:.4f}"),
                ("Objetivo de retorno", f"Objetivo={target:.4f}, cartera cercana: retorno={near['expected_return']:.4f}, vol={near['volatility']:.4f}" if not eff.empty else f"Objetivo={target:.4f}"),
                ("Diversificacion", "La correlacion entre activos permite reducir riesgo total."),
                ("Lectura integrada", interp),
            ],
        )

    with tabs[6]:
        st.subheader("Modulo 7 - Senales")
        st.latex(r"\text{Senal} = f(\text{MACD cross}, RSI, BB, MA\ cross, \%K/\%D)")

        c1, c2, c3 = st.columns(3)
        rsi_over = c1.slider("RSI sobrecompra", min_value=50.0, max_value=95.0, value=70.0)
        rsi_under = c2.slider("RSI sobreventa", min_value=5.0, max_value=50.0, value=30.0)
        short_ma = c3.slider("Media corta", min_value=5, max_value=150, value=50)
        c4, c5, c6 = st.columns(3)
        stoch_over = c4.slider("Estocastico sobrecompra", min_value=50.0, max_value=100.0, value=80.0)
        stoch_under = c5.slider("Estocastico sobreventa", min_value=0.0, max_value=50.0, value=20.0)
        long_ma = c6.slider("Media larga", min_value=20, max_value=300, value=200)

        alerts = api_get(
            base_url,
            "/alertas",
            params={
                "tickers": ",".join(tickers),
                "rsi_overbought": rsi_over,
                "rsi_oversold": rsi_under,
                "stoch_overbought": stoch_over,
                "stoch_oversold": stoch_under,
                "short_ma_window": short_ma,
                "long_ma_window": long_ma,
            },
        )

        counts = pd.Series([a["signal"] for a in alerts["alerts"]]).value_counts()
        csum1, csum2, csum3, csum4 = st.columns(4)
        csum1.metric("Compra", int(counts.get("buy", 0)))
        csum2.metric("Venta", int(counts.get("sell", 0)))
        csum3.metric("Mixta", int(counts.get("mixed", 0)))
        csum4.metric("Neutral", int(counts.get("neutral", 0)))
        st.caption("Semaforo: verde=compra, rojo=venta, ambar=mixta, gris=neutral")

        cols = st.columns(max(1, min(5, len(alerts["alerts"]) or 1)))
        for i, a in enumerate(alerts["alerts"]):
            color = {
                "buy": "#c7f9cc",
                "sell": "#ffccd5",
                "mixed": "#ffe8b6",
                "neutral": "#e9ecef",
            }.get(a["signal"], "#e9ecef")
            reasons = "<br>".join(a["reasons"])
            card = f"""
            <div style='background:{color};padding:12px;border-radius:10px;border:1px solid #adb5bd;'>
                <h4 style='margin:0 0 8px 0'>{a['ticker']} - {a['signal'].upper()}</h4>
                <p style='margin:0'>{reasons}</p>
            </div>
            """
            cols[i % len(cols)].markdown(card, unsafe_allow_html=True)

        alert_rows = []
        for a in alerts["alerts"]:
            if a["signal"] == "buy":
                lectura = "Predominan condiciones alcistas de corto plazo; evaluar entrada gradual con control de riesgo."
            elif a["signal"] == "sell":
                lectura = "Predominan condiciones bajistas/sobrecompra; considerar reduccion de exposicion o toma de utilidades."
            elif a["signal"] == "mixed":
                lectura = "Hay senales cruzadas; conviene confirmar con horizonte y perfil de riesgo antes de decidir."
            else:
                lectura = "No hay senal tecnica dominante; mantener monitoreo hasta un nuevo disparador."

            alert_rows.append(
                {
                    "Ticker": a["ticker"],
                    "Senal": a["signal"],
                    "Detalle": " | ".join(a["reasons"]),
                    "Interpretacion automatica": lectura,
                }
            )
        st.dataframe(pd.DataFrame(alert_rows), use_container_width=True)

        interp = (
            "El sistema traduce los indicadores tecnicos a reglas operativas: cruces MACD, zonas extremas RSI, toques de Bollinger, "
            "golden/death cross y cruces estocasticos en extremos; con umbrales configurables, el panel resume por activo una senal accionable "
            "(compra, venta, mixta o neutral) en lenguaje simple para facilitar decisiones tacticas."
        )
        render_analysis_table(
            "Interpretacion de senales tecnicas",
            [
                ("Umbrales RSI", f"Sobrecompra>{rsi_over:.1f}, Sobreventa<{rsi_under:.1f}"),
                ("Umbrales Estocastico", f"Sobrecompra>{stoch_over:.1f}, Sobreventa<{stoch_under:.1f}"),
                ("Medias moviles", f"Corta={short_ma}, Larga={long_ma}"),
                (
                    "Resumen de senales",
                    f"Compra={int(counts.get('buy', 0))}, Venta={int(counts.get('sell', 0))}, Mixta={int(counts.get('mixed', 0))}, Neutral={int(counts.get('neutral', 0))}",
                ),
                ("Lectura integrada", interp),
            ],
        )

    with tabs[7]:
        st.subheader("Modulo 8 - Macro y benchmark")
        st.latex(r"\alpha_J = R_p - \left[R_f + \beta_p(R_m - R_f)\right],\quad IR=\frac{R_p-R_b}{TE}")

        macro = api_get(base_url, "/macro")
        m1, m2, m3 = st.columns(3)
        m1.metric("Tasa libre de riesgo anual", f"{macro['risk_free_rate_annual']:.2%}")
        m2.metric("Inflacion YoY", f"{macro['inflation_yoy']:.2%}")
        m3.metric("USD/COP", f"{macro['usd_cop']:.2f}")

        frontier = api_post(base_url, "/frontera-eficiente", payload={"tickers": tickers, "n_portfolios": 10000})
        w_opt = frontier["max_sharpe"]["weights"]

        ret_mat = returns_matrix(base_url, tickers + [benchmark] if benchmark not in tickers else tickers, start_date, end_date)
        if benchmark not in ret_mat.columns:
            st.error("No se pudo construir benchmark")
            st.stop()

        weights_opt = np.array([w_opt.get(t, 0.0) for t in tickers])
        rp = pd.Series(ret_mat[tickers].values @ weights_opt, index=ret_mat.index, name="portfolio")
        rb = ret_mat[benchmark].rename("benchmark")
        joined = pd.concat([rp, rb], axis=1).dropna()

        base = 100.0
        cum = pd.DataFrame(
            {
                "Portafolio optimo": base * (1 + joined["portfolio"]).cumprod(),
                f"Benchmark {benchmark}": base * (1 + joined["benchmark"]).cumprod(),
            }
        )
        fig_cum = go.Figure()
        for c in cum.columns:
            fig_cum.add_trace(go.Scatter(x=cum.index, y=cum[c], mode="lines", name=c))
        fig_cum.update_layout(height=430, yaxis_title="Indice base 100")
        st.plotly_chart(fig_cum, use_container_width=True)

        rf_daily = macro["risk_free_rate_annual"] / 252.0
        rp_ann = float(joined["portfolio"].mean() * 252)
        rb_ann = float(joined["benchmark"].mean() * 252)
        vp_ann = float(joined["portfolio"].std(ddof=1) * np.sqrt(252))
        vb_ann = float(joined["benchmark"].std(ddof=1) * np.sqrt(252))
        sharpe_p = float((rp_ann - macro["risk_free_rate_annual"]) / vp_ann) if vp_ann > 0 else np.nan
        sharpe_b = float((rb_ann - macro["risk_free_rate_annual"]) / vb_ann) if vb_ann > 0 else np.nan

        cov_pb = np.cov(joined["portfolio"], joined["benchmark"], ddof=1)[0, 1]
        var_b = np.var(joined["benchmark"], ddof=1)
        beta_p = float(cov_pb / var_b) if var_b > 0 else 0.0
        alpha_jensen = float(rp_ann - (macro["risk_free_rate_annual"] + beta_p * (rb_ann - macro["risk_free_rate_annual"])))

        # Significance test for Jensen alpha via CAPM regression on daily excess returns.
        x_excess = (joined["benchmark"] - rf_daily).values
        y_excess = (joined["portfolio"] - rf_daily).values
        n_obs = len(x_excess)
        alpha_daily = np.nan
        alpha_t = np.nan
        alpha_p = np.nan
        if n_obs > 2:
            x_mean = float(np.mean(x_excess))
            y_mean = float(np.mean(y_excess))
            sxx = float(np.sum((x_excess - x_mean) ** 2))
            if sxx > 0:
                beta_reg = float(np.sum((x_excess - x_mean) * (y_excess - y_mean)) / sxx)
                alpha_daily = float(y_mean - beta_reg * x_mean)
                resid = y_excess - (alpha_daily + beta_reg * x_excess)
                s2 = float(np.sum(resid**2) / (n_obs - 2))
                var_alpha = s2 * ((1.0 / n_obs) + (x_mean**2 / sxx))
                if var_alpha > 0:
                    alpha_se = float(np.sqrt(var_alpha))
                    alpha_t = float(alpha_daily / alpha_se)
                    alpha_p = float(2 * (1 - stats.t.cdf(abs(alpha_t), df=n_obs - 2)))

        alpha_significant = bool(np.isfinite(alpha_p) and alpha_p < 0.05)

        active = joined["portfolio"] - joined["benchmark"]
        tracking_error = float(active.std(ddof=1) * np.sqrt(252))
        info_ratio = float((rp_ann - rb_ann) / tracking_error) if tracking_error > 0 else np.nan

        def max_drawdown(series: pd.Series) -> float:
            curve = (1 + series).cumprod()
            peak = curve.cummax()
            dd = curve / peak - 1
            return float(dd.min())

        perf = pd.DataFrame(
            {
                "Serie": ["Portafolio optimo", f"Benchmark {benchmark}"],
                "Rendimiento acumulado": [cum.iloc[-1, 0] / 100 - 1, cum.iloc[-1, 1] / 100 - 1],
                "Rendimiento anualizado": [rp_ann, rb_ann],
                "Volatilidad anualizada": [vp_ann, vb_ann],
                "Sharpe": [sharpe_p, sharpe_b],
                "Max Drawdown": [max_drawdown(joined["portfolio"]), max_drawdown(joined["benchmark"])],
            }
        )
        st.dataframe(perf.style.format({
            "Rendimiento acumulado": "{:.2%}",
            "Rendimiento anualizado": "{:.2%}",
            "Volatilidad anualizada": "{:.2%}",
            "Sharpe": "{:.3f}",
            "Max Drawdown": "{:.2%}",
        }), use_container_width=True)

        alpha_diag = pd.DataFrame(
            [
                {
                    "Alpha Jensen anual": alpha_jensen,
                    "Alpha diario (regresion)": alpha_daily,
                    "t-stat alpha": alpha_t,
                    "p-value alpha": alpha_p,
                    "Significativo 5%": "SI" if alpha_significant else "NO",
                }
            ]
        )
        st.dataframe(
            alpha_diag.style.format(
                {
                    "Alpha Jensen anual": "{:.4f}",
                    "Alpha diario (regresion)": "{:.6f}",
                    "t-stat alpha": "{:.4f}",
                    "p-value alpha": "{:.4f}",
                }
            ),
            use_container_width=True,
        )

        interp = (
            f"El panel macro integra Rf={macro['risk_free_rate_annual']:.2%}, inflacion e USD/COP desde API; al comparar el portafolio optimo con {benchmark} en base 100, "
            f"se obtiene alpha de Jensen {alpha_jensen:.4f}, tracking error {tracking_error:.4f} e information ratio {info_ratio:.4f}, lo que permite concluir "
            f"que el portafolio {'supera' if perf.iloc[0]['Rendimiento acumulado'] > perf.iloc[1]['Rendimiento acumulado'] else 'no supera'} al benchmark en el periodo analizado en terminos riesgo-retorno; "
            f"ademas, el alpha {'es significativo' if alpha_significant else 'no es estadisticamente significativo'} al 5%."
        )
        render_analysis_table(
            "Interpretacion macro y benchmarking",
            [
                ("Contexto macro", f"Rf={macro['risk_free_rate_annual']:.2%}, Inflacion={macro['inflation_yoy']:.2%}, USD/COP={macro['usd_cop']:.2f}"),
                ("Alpha de Jensen", f"{alpha_jensen:.4f}"),
                ("Tracking Error", f"{tracking_error:.4f}"),
                ("Information Ratio", f"{info_ratio:.4f}"),
                ("Significancia del alpha", "Significativo al 5%" if alpha_significant else "No significativo al 5%"),
                (
                    "Comparacion vs benchmark",
                    "El portafolio supera al benchmark" if perf.iloc[0]["Rendimiento acumulado"] > perf.iloc[1]["Rendimiento acumulado"] else "El portafolio no supera al benchmark",
                ),
                ("Lectura integrada", interp),
            ],
        )


if __name__ == "__main__":
    main()
