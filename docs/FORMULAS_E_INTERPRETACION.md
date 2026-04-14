# Formulas e interpretacion

## 1) Rendimientos
- Simple return: r_t = (P_t / P_{t-1}) - 1
- Log return: l_t = ln(P_t / P_{t-1})

Interpretacion:
- Rendimiento simple facilita lectura porcentual diaria.
- Log-rendimiento es aditivo en el tiempo y estable para modelado.

## 2) Indicadores tecnicos
- SMA(n): promedio movil simple de n periodos.
- EMA(n): promedio movil exponencial con mayor peso reciente.
- RSI(14): 100 - 100 / (1 + RS).
- MACD: EMA(12) - EMA(26), con Signal EMA(9).
- Bollinger: media movil +/- k desviaciones.
- Estocastico: %K y %D en rango [0,100].

Interpretacion:
- RSI > 70 sugiere sobrecompra; RSI < 30 sugiere sobreventa.
- Cruce MACD sobre signal sugiere impulso alcista.
- Precio fuera de bandas puede indicar sobreextension.

## 3) CAPM
- E[R_i] = R_f + beta_i (E[R_m] - R_f)
- beta_i = Cov(R_i, R_m) / Var(R_m)

Interpretacion:
- beta > 1: activo agresivo.
- beta < 1: activo defensivo.
- alpha de Jensen positiva sugiere superacion ajustada por riesgo.

## 4) VaR y CVaR
- VaR al nivel c: cuantila de perdidas al nivel (1-c).
- CVaR: perdida promedio en la cola peor a VaR.

Metodos implementados:
- Parametrico (normal)
- Historico
- Monte Carlo

Interpretacion:
- VaR 95% = perdida umbral esperada que solo se supera en 5% de casos.
- CVaR suele ser mayor que VaR y refleja severidad de cola.

## 5) Markowitz
- Rendimiento esperado portafolio: mu_p = w' * mu
- Volatilidad: sigma_p = sqrt(w' * Sigma * w)
- Sharpe: (mu_p - R_f)/sigma_p (en el frontend se usa aproximacion sin R_f para comparacion relativa)

Interpretacion:
- Minima varianza minimiza riesgo.
- Max Sharpe maximiza retorno por unidad de riesgo.
- Frontera eficiente contiene combinaciones no dominadas.

## 6) Volatilidad condicional
Modelos:
- ARCH(1)
- GARCH(1,1)
- EGARCH(1,1)

Criterio:
- Se elige el mejor por AIC (menor es mejor).

Interpretacion:
- Clustering de volatilidad valida uso GARCH.
- Pronostico de sigma ayuda a gestionar riesgo de corto plazo.
