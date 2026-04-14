from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from scipy import stats


st.set_page_config(page_title="RiskLab USTA", layout="wide")

API_BASE_URL = st.sidebar.text_input("Backend URL", value="http://127.0.0.1:8000")
DEFAULT_TICKERS = ["NVDA", "BCOLO.CB", "ECOPETROL.CB", "KO", "SPY"]


def show_module_intro(module_name: str, objective: str, formulas: list[str], interpretation: str) -> None:
    st.markdown(f"### {module_name}")
    st.info(f"Objetivo: {objective}")
    with st.expander("Ver formulas e interpretacion"):
        st.markdown("**Formulas clave**")
        for formula in formulas:
            st.markdown(f"- {formula}")
        st.markdown("**Interpretacion**")
        st.write(interpretation)


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
st.sidebar.markdown("### Estado del frontend")
st.sidebar.write("- Archivo: frontend/app.py")
st.sidebar.write("- Framework: Streamlit")
st.sidebar.write("- Navegacion: tabs (8 modulos)")
st.sidebar.write("- Fuente de datos: backend FastAPI")
st.sidebar.write("- Backend URL configurable en esta barra lateral")

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
    show_module_intro(
        module_name="Modulo 1 - Analisis tecnico",
        objective="Explorar comportamiento historico e indicadores tecnicos por activo.",
        formulas=[
            "SMA(n) = promedio movil simple de n periodos.",
            "EMA(n) = promedio movil exponencial con mayor peso reciente.",
            "RSI = 100 - 100 / (1 + RS).",
            "MACD = EMA(12) - EMA(26).",
        ],
        interpretation="RSI mayor a 70 sugiere sobrecompra, menor a 30 sugiere sobreventa. Cruces MACD/Signal apoyan lectura de impulso.",
    )
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

        st.markdown("**Ultimos valores de indicadores**")
        cols = ["date", "close", "sma", "ema", "rsi", "macd", "macd_signal", "bb_upper", "bb_lower", "stoch_k", "stoch_d"]
        st.dataframe(df[cols].tail(5), use_container_width=True)


with tabs[1]:
    show_module_intro(
        module_name="Modulo 2 - Rendimientos y propiedades empiricas",
        objective="Caracterizar distribucion de rendimientos y validar normalidad.",
        formulas=[
            "r_t simple = (P_t / P_{t-1}) - 1",
            "r_t log = ln(P_t / P_{t-1})",
            "Pruebas: Jarque-Bera y Shapiro-Wilk",
        ],
        interpretation="Si p-value < 0.05 se rechaza normalidad. Esto apoya uso de modelos de riesgo con colas pesadas.",
    )
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

        qq_x = np.sort(df["simple_return"].values)
        n = len(qq_x)
        probs = (np.arange(1, n + 1) - 0.5) / n
        qq_theoretical = stats.norm.ppf(probs, loc=np.mean(qq_x), scale=np.std(qq_x, ddof=1))
        qq_fig = go.Figure()
        qq_fig.add_trace(go.Scatter(x=qq_theoretical, y=qq_x, mode="markers", name="Datos"))
        qq_fig.add_trace(
            go.Scatter(
                x=[qq_theoretical.min(), qq_theoretical.max()],
                y=[qq_theoretical.min(), qq_theoretical.max()],
                mode="lines",
                name="Referencia Normal",
                line=dict(dash="dash"),
            )
        )
        qq_fig.update_layout(title="Q-Q plot vs Normal", xaxis_title="Cuantiles teoricos", yaxis_title="Cuantiles muestrales")
        st.plotly_chart(qq_fig, use_container_width=True)

        jb_msg = "No normal" if stats_data["jarque_bera_pvalue"] < 0.05 else "Normal"
        shapiro_msg = "No normal" if stats_data["shapiro_pvalue"] < 0.05 else "Normal"
        st.info(f"Interpretacion JB: {jb_msg} | Interpretacion Shapiro: {shapiro_msg}")

        skew = float(stats_data["skewness"])
        kurt = float(stats_data["kurtosis"])
        if abs(skew) > 0.5:
            skew_msg = "asimetria relevante"
        else:
            skew_msg = "asimetria baja"
        if kurt > 3:
            kurt_msg = "colas pesadas"
        else:
            kurt_msg = "colas moderadas"
        st.write(
            f"Hechos estilizados: {skew_msg} (skew={skew:.3f}), {kurt_msg} (kurtosis={kurt:.3f})."
        )


with tabs[2]:
    show_module_intro(
        module_name="Modulo 3 - ARCH/GARCH",
        objective="Modelar volatilidad condicional y comparar modelos por criterios de informacion.",
        formulas=[
            "Comparacion por AIC y BIC (menor es mejor).",
            "Pronostico de volatilidad a un paso.",
        ],
        interpretation="El mejor modelo por AIC se usa para estimar volatilidad esperada de corto plazo.",
    )
    data = safe_get(
        f"/volatilidad/{main_ticker}",
        params={"start_date": str(start_date), "end_date": str(end_date)},
    )
    if data:
        models = pd.DataFrame(data["models"]).sort_values("aic")
        st.dataframe(models, use_container_width=True)
        fig_ic = px.bar(models, x="model_name", y=["aic", "bic"], barmode="group", title="Comparacion AIC/BIC")
        st.plotly_chart(fig_ic, use_container_width=True)
        st.markdown("**Diagnostico de residuos estandarizados (modelo seleccionado)**")
        st.write(
            {
                "jarque_bera_stat": data.get("residuals_jarque_bera_stat"),
                "jarque_bera_pvalue": data.get("residuals_jarque_bera_pvalue"),
            }
        )
        resid = pd.Series(data.get("standardized_residuals", []), name="std_resid")
        if not resid.empty:
            resid_fig = px.line(resid, y="std_resid", title="Residuos estandarizados")
            st.plotly_chart(resid_fig, use_container_width=True)
        st.success(
            f"Mejor modelo por AIC: {data['best_model']} | Pronostico volatilidad proximo dia: {data['forecast_next_day_volatility']:.4f}"
        )


with tabs[3]:
    show_module_intro(
        module_name="Modulo 4 - CAPM y beta",
        objective="Cuantificar riesgo sistematico y rendimiento esperado por activo.",
        formulas=[
            "beta_i = Cov(R_i, R_m) / Var(R_m)",
            "E[R_i] = R_f + beta_i * (E[R_m] - R_f)",
        ],
        interpretation="beta > 1 indica activo mas sensible al mercado; beta < 1 sugiere perfil defensivo.",
    )
    data = safe_get("/capm", params={"tickers": ",".join([t for t in tickers if t != "SPY"]), "benchmark": "SPY"})
    if data:
        assets = pd.DataFrame(data["assets"])
        st.metric("Tasa libre de riesgo anual", f"{data['risk_free_rate']:.2%}")
        st.dataframe(assets, use_container_width=True)

        if not assets.empty:
            fig = px.bar(assets, x="ticker", y="beta", color="classification", title="Betas por activo")
            st.plotly_chart(fig, use_container_width=True)

            scatter = px.scatter(
                assets,
                x="beta",
                y="annualized_return_asset",
                color="classification",
                text="ticker",
                title="Relacion Beta vs Retorno anualizado",
            )
            st.plotly_chart(scatter, use_container_width=True)


with tabs[4]:
    show_module_intro(
        module_name="Modulo 5 - VaR y CVaR",
        objective="Cuantificar perdida potencial diaria y anualizada del portafolio.",
        formulas=[
            "VaR al nivel c usa cola alpha = 1 - c.",
            "CVaR = perdida promedio condicionada a exceder VaR.",
            "VaR anualizado ~= VaR diario * sqrt(252).",
        ],
        interpretation="CVaR complementa VaR al capturar severidad de eventos extremos, no solo umbral.",
    )
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
                st.markdown("**Resultados numericos**")
                st.dataframe(pd.DataFrame([data]), use_container_width=True)
                fig = go.Figure(
                    data=[
                        go.Bar(name="Parametrico", x=["VaR Diario"], y=[data["var_parametric"]]),
                        go.Bar(name="Historico", x=["VaR Diario"], y=[data["var_historical"]]),
                        go.Bar(name="Monte Carlo", x=["VaR Diario"], y=[data["var_monte_carlo"]]),
                        go.Bar(name="Parametrico Anual", x=["VaR Anualizado"], y=[data["var_parametric_annualized"]]),
                        go.Bar(name="Historico Anual", x=["VaR Anualizado"], y=[data["var_historical_annualized"]]),
                        go.Bar(name="Monte Carlo Anual", x=["VaR Anualizado"], y=[data["var_monte_carlo_annualized"]]),
                        go.Bar(name="CVaR Hist", x=["CVaR"], y=[data["cvar_historical"]]),
                    ]
                )
                st.plotly_chart(fig, use_container_width=True)

                # Visual tipo distribucion con lineas de VaR y CVaR en escala de perdida
                loss_points = np.linspace(0, max(data["var_monte_carlo"] * 2, data["cvar_historical"] * 1.5, 1e-4), 100)
                density = stats.norm.pdf(loss_points, loc=data["var_parametric"] / 2, scale=max(data["var_parametric"] / 3, 1e-6))
                dens_fig = go.Figure()
                dens_fig.add_trace(go.Scatter(x=loss_points, y=density, mode="lines", name="Densidad ilustrativa"))
                dens_fig.add_vline(x=data["var_parametric"], line_dash="dash", annotation_text="VaR Param")
                dens_fig.add_vline(x=data["var_historical"], line_dash="dash", annotation_text="VaR Hist")
                dens_fig.add_vline(x=data["var_monte_carlo"], line_dash="dash", annotation_text="VaR MC")
                dens_fig.add_vline(x=data["cvar_historical"], line_dash="dot", annotation_text="CVaR")
                dens_fig.update_layout(title="Distribucion de perdida (ilustrativa) con lineas VaR/CVaR", xaxis_title="Perdida", yaxis_title="Densidad")
                st.plotly_chart(dens_fig, use_container_width=True)


with tabs[5]:
    show_module_intro(
        module_name="Modulo 6 - Frontera eficiente de Markowitz",
        objective="Encontrar combinaciones optimas de riesgo-retorno del portafolio.",
        formulas=[
            "mu_p = w' * mu",
            "sigma_p = sqrt(w' * Sigma * w)",
            "Sharpe = retorno / volatilidad (aprox usada en la API)",
        ],
        interpretation="La frontera eficiente contiene portafolios no dominados. Se reportan minima varianza y maximo Sharpe.",
    )
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
    show_module_intro(
        module_name="Modulo 7 - Senales y alertas",
        objective="Generar alertas de compra/venta en lenguaje simple por activo.",
        formulas=[
            "MACD crossover bullish/bearish",
            "RSI extremo: >70 sobrecompra, <30 sobreventa",
            "Precio vs bandas de Bollinger",
        ],
        interpretation="Las senales sintetizan multiples indicadores en recomendaciones buy/sell/mixed/neutral.",
    )
    data = safe_get("/alertas", params={"tickers": ",".join([t for t in tickers if t != "SPY"])})
    if data:
        for alert in data["alerts"]:
            color = {"buy": "green", "sell": "red", "mixed": "orange", "neutral": "gray"}.get(alert["signal"], "gray")
            st.markdown(f"### {alert['ticker']} - :{color}[{alert['signal'].upper()}]")
            for reason in alert["reasons"]:
                st.write(f"- {reason}")


with tabs[7]:
    show_module_intro(
        module_name="Modulo 8 - Macro y benchmark",
        objective="Comparar portafolio vs benchmark e incorporar contexto macroeconomico.",
        formulas=[
            "Alpha de Jensen",
            "Tracking Error",
            "Information Ratio",
            "Sharpe y Max Drawdown",
        ],
        interpretation="Se evalua si el portafolio supera al benchmark ajustando por riesgo.",
    )
    macro = safe_get("/macro")
    portfolio_tickers = [t for t in tickers if t != "SPY"]
    capm_data = safe_get("/capm", params={"tickers": ",".join(portfolio_tickers), "benchmark": "SPY"})
    benchmark_data = safe_get("/benchmark", params={"tickers": ",".join(portfolio_tickers), "benchmark": "SPY"}) if portfolio_tickers else None
    if macro:
        c1, c2, c3 = st.columns(3)
        c1.metric("Rf anual", f"{macro['risk_free_rate_annual']:.2%}")
        c2.metric("Inflacion YoY", f"{macro['inflation_yoy']:.2%}")
        c3.metric("USD/COP", f"{macro['usd_cop']:.2f}")

    if benchmark_data:
        c1, c2, c3 = st.columns(3)
        c1.metric("Alpha Jensen", f"{benchmark_data['alpha_jensen']:.2%}")
        c2.metric("Tracking Error", f"{benchmark_data['tracking_error']:.2%}")
        c3.metric("Information Ratio", f"{benchmark_data['information_ratio']:.3f}")

        c4, c5, c6 = st.columns(3)
        c4.metric("Sharpe Portafolio", f"{benchmark_data['sharpe_portfolio']:.3f}")
        c5.metric("Sharpe Benchmark", f"{benchmark_data['sharpe_benchmark']:.3f}")
        c6.metric("MDD Portafolio", f"{benchmark_data['max_drawdown_portfolio']:.2%}")

        curve_df = pd.DataFrame(
            {
                "Portafolio": benchmark_data["cumulative_portfolio_base100"],
                "Benchmark": benchmark_data["cumulative_benchmark_base100"],
            }
        )
        curve_df["Index"] = range(len(curve_df))
        fig_curve = px.line(curve_df, x="Index", y=["Portafolio", "Benchmark"], title="Rendimiento acumulado base 100")
        st.plotly_chart(fig_curve, use_container_width=True)

    if capm_data and capm_data["assets"]:
        assets = pd.DataFrame(capm_data["assets"])
        fig = px.bar(assets, x="ticker", y=["annualized_return_asset", "expected_return_capm"], barmode="group")
        st.plotly_chart(fig, use_container_width=True)
