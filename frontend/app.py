from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st


st.set_page_config(page_title="RiskLab USTA", layout="wide")

API_BASE_URL = st.sidebar.text_input("Backend URL", value="http://127.0.0.1:8000")
DEFAULT_TICKERS = ["NVDA", "BCOLO.CB", "ECOPETROL.CB", "KO", "SPY"]


@st.cache_data(ttl=300)
def api_get(path: str, params: dict | None = None) -> dict:
    response = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=300)
def api_post(path: str, payload: dict) -> dict:
    response = requests.post(f"{API_BASE_URL}{path}", json=payload, timeout=60)
    response.raise_for_status()
    return response.json()


def safe_get(path: str, params: dict | None = None) -> dict | None:
    try:
        return api_get(path, params=params)
    except Exception as exc:  # noqa: BLE001
        st.error(f"API error at {path}: {exc}")
        return None


def safe_post(path: str, payload: dict) -> dict | None:
    try:
        return api_post(path, payload=payload)
    except Exception as exc:  # noqa: BLE001
        st.error(f"API error at {path}: {exc}")
        return None


st.title("Proyecto Integrador - Teoria del Riesgo")
st.caption("Frontend Streamlit consumiendo backend FastAPI")

col_a, col_b, col_c = st.columns(3)
with col_a:
    start_date = st.date_input("Fecha inicio", value=date(2023, 1, 1))
with col_b:
    end_date = st.date_input("Fecha fin", value=date.today())
with col_c:
    tickers_input = st.text_input("Tickers (coma)", value=",".join(DEFAULT_TICKERS))

tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
main_ticker = st.selectbox("Activo principal", options=tickers or DEFAULT_TICKERS, index=0)


tabs = st.tabs(
    [
        "1. Analisis tecnico",
        "2. Rendimientos",
        "3. ARCH/GARCH",
        "4. CAPM",
        "5. VaR/CVaR",
        "6. Markowitz",
        "7. Senales",
        "8. Macro/Benchmark",
    ]
)


with tabs[0]:
    st.subheader("Modulo 1 - Analisis tecnico")
    data = safe_get(
        f"/indicadores/{main_ticker}",
        params={"start_date": str(start_date), "end_date": str(end_date)},
    )
    if data:
        df = pd.DataFrame(data["points"])
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["date"], y=df["close"], name="Close"))
        fig.add_trace(go.Scatter(x=df["date"], y=df["sma"], name="SMA"))
        fig.add_trace(go.Scatter(x=df["date"], y=df["ema"], name="EMA"))
        fig.add_trace(go.Scatter(x=df["date"], y=df["bb_upper"], name="BB Upper", line=dict(dash="dot")))
        fig.add_trace(go.Scatter(x=df["date"], y=df["bb_lower"], name="BB Lower", line=dict(dash="dot")))
        st.plotly_chart(fig, use_container_width=True)

        st.write("RSI")
        fig_rsi = px.line(df, x="date", y="rsi")
        fig_rsi.add_hline(y=70, line_dash="dash")
        fig_rsi.add_hline(y=30, line_dash="dash")
        st.plotly_chart(fig_rsi, use_container_width=True)

        st.write("MACD")
        fig_macd = go.Figure()
        fig_macd.add_trace(go.Scatter(x=df["date"], y=df["macd"], name="MACD"))
        fig_macd.add_trace(go.Scatter(x=df["date"], y=df["macd_signal"], name="Signal"))
        fig_macd.add_trace(go.Bar(x=df["date"], y=df["macd_hist"], name="Hist"))
        st.plotly_chart(fig_macd, use_container_width=True)


with tabs[1]:
    st.subheader("Modulo 2 - Rendimientos y propiedades empiricas")
    data = safe_get(
        f"/rendimientos/{main_ticker}",
        params={"start_date": str(start_date), "end_date": str(end_date)},
    )
    if data:
        df = pd.DataFrame(data["points"])
        stats_data = data["stats"]

        st.write("Estadisticas descriptivas")
        st.json(stats_data)

        col1, col2 = st.columns(2)
        with col1:
            fig_hist = px.histogram(df, x="simple_return", nbins=50, title="Histograma de rendimientos")
            st.plotly_chart(fig_hist, use_container_width=True)
        with col2:
            fig_box = px.box(df, y="simple_return", title="Boxplot")
            st.plotly_chart(fig_box, use_container_width=True)

        st.line_chart(df.set_index("date")[["simple_return", "log_return"]])

        jb_msg = "No normal" if stats_data["jarque_bera_pvalue"] < 0.05 else "Normal"
        shapiro_msg = "No normal" if stats_data["shapiro_pvalue"] < 0.05 else "Normal"
        st.info(f"Interpretacion JB: {jb_msg} | Interpretacion Shapiro: {shapiro_msg}")


with tabs[2]:
    st.subheader("Modulo 3 - ARCH/GARCH")
    data = safe_get(
        f"/volatilidad/{main_ticker}",
        params={"start_date": str(start_date), "end_date": str(end_date)},
    )
    if data:
        models = pd.DataFrame(data["models"]).sort_values("aic")
        st.dataframe(models, use_container_width=True)
        st.success(
            f"Mejor modelo por AIC: {data['best_model']} | Pronostico volatilidad proximo dia: {data['forecast_next_day_volatility']:.4f}"
        )


with tabs[3]:
    st.subheader("Modulo 4 - CAPM y beta")
    data = safe_get("/capm", params={"tickers": ",".join([t for t in tickers if t != "SPY"]), "benchmark": "SPY"})
    if data:
        assets = pd.DataFrame(data["assets"])
        st.metric("Tasa libre de riesgo anual", f"{data['risk_free_rate']:.2%}")
        st.dataframe(assets, use_container_width=True)

        if not assets.empty:
            fig = px.bar(assets, x="ticker", y="beta", color="classification", title="Betas por activo")
            st.plotly_chart(fig, use_container_width=True)


with tabs[4]:
    st.subheader("Modulo 5 - VaR y CVaR")
    selected = st.multiselect("Activos para VaR", options=tickers, default=tickers[: min(5, len(tickers))])
    if selected:
        weight_default = [round(1 / len(selected), 4)] * len(selected)
        weights_text = st.text_input("Pesos (coma)", value=",".join(str(x) for x in weight_default))
        confidence = st.slider("Nivel de confianza", min_value=0.90, max_value=0.99, value=0.95, step=0.01)
        try:
            weights = [float(x.strip()) for x in weights_text.split(",")]
        except ValueError:
            weights = []

        if st.button("Calcular VaR/CVaR"):
            payload = {"tickers": selected, "weights": weights, "confidence": confidence}
            data = safe_post("/var", payload)
            if data:
                st.json(data)
                fig = go.Figure(
                    data=[
                        go.Bar(name="Parametrico", x=["VaR"], y=[data["var_parametric"]]),
                        go.Bar(name="Historico", x=["VaR"], y=[data["var_historical"]]),
                        go.Bar(name="Monte Carlo", x=["VaR"], y=[data["var_monte_carlo"]]),
                        go.Bar(name="CVaR Hist", x=["CVaR"], y=[data["cvar_historical"]]),
                    ]
                )
                st.plotly_chart(fig, use_container_width=True)


with tabs[5]:
    st.subheader("Modulo 6 - Frontera eficiente de Markowitz")
    selected = st.multiselect("Activos", options=tickers, default=tickers[: min(5, len(tickers))], key="m6")
    n_portfolios = st.slider("Numero de portafolios", min_value=3000, max_value=30000, value=10000, step=1000)
    if st.button("Calcular frontera eficiente"):
        data = safe_post("/frontera-eficiente", {"tickers": selected, "n_portfolios": n_portfolios})
        if data:
            points = pd.DataFrame(data["points"])
            efficient = pd.DataFrame(data["efficient_frontier"])
            fig = px.scatter(points, x="volatility", y="expected_return", color="sharpe", title="Conjunto factible")
            fig.add_trace(
                go.Scatter(
                    x=efficient["volatility"],
                    y=efficient["expected_return"],
                    mode="lines",
                    name="Frontera eficiente",
                    line=dict(color="red", width=3),
                )
            )
            st.plotly_chart(fig, use_container_width=True)
            st.write("Portafolio de minima varianza")
            st.json(data["min_variance"])
            st.write("Portafolio de maximo Sharpe")
            st.json(data["max_sharpe"])


with tabs[6]:
    st.subheader("Modulo 7 - Senales y alertas")
    data = safe_get("/alertas", params={"tickers": ",".join([t for t in tickers if t != "SPY"])})
    if data:
        for alert in data["alerts"]:
            color = {"buy": "green", "sell": "red", "mixed": "orange", "neutral": "gray"}.get(alert["signal"], "gray")
            st.markdown(f"### {alert['ticker']} - :{color}[{alert['signal'].upper()}]")
            for reason in alert["reasons"]:
                st.write(f"- {reason}")


with tabs[7]:
    st.subheader("Modulo 8 - Macro y benchmark")
    macro = safe_get("/macro")
    capm_data = safe_get("/capm", params={"tickers": ",".join([t for t in tickers if t != "SPY"]), "benchmark": "SPY"})
    if macro:
        c1, c2, c3 = st.columns(3)
        c1.metric("Rf anual", f"{macro['risk_free_rate_annual']:.2%}")
        c2.metric("Inflacion YoY", f"{macro['inflation_yoy']:.2%}")
        c3.metric("USD/COP", f"{macro['usd_cop']:.2f}")

    if capm_data and capm_data["assets"]:
        assets = pd.DataFrame(capm_data["assets"])
        mean_port_return = assets["annualized_return_asset"].mean()
        market_return = assets["annualized_return_market"].iloc[0]
        rf = capm_data["risk_free_rate"]
        beta_port = assets["beta"].mean()
        alpha_jensen = mean_port_return - (rf + beta_port * (market_return - rf))

        st.write("Metricas benchmark")
        st.write(
            {
                "alpha_jensen": float(alpha_jensen),
                "tracking_error_aprox": float((assets["annualized_return_asset"] - market_return).std(ddof=0)),
                "information_ratio_aprox": float(
                    (mean_port_return - market_return)
                    / max((assets["annualized_return_asset"] - market_return).std(ddof=0), 1e-8)
                ),
            }
        )

        fig = px.bar(assets, x="ticker", y=["annualized_return_asset", "expected_return_capm"], barmode="group")
        st.plotly_chart(fig, use_container_width=True)
