# Informe Ejecutivo - Proyecto Teoria del Riesgo

## 1. Portada
- Proyecto: Analitica de riesgo financiero con APIs
- Curso: Teoria del Riesgo
- Universidad: USTA
- Integrantes: [Nombre 1] y [Nombre 2]
- Profesor: Javier Mauricio Sierra
- Fecha: [Completar]

## 2. Resumen ejecutivo
Se desarrollo una solucion de analitica de riesgo financiero con arquitectura separada backend/frontend. El backend en FastAPI centraliza calculos y consumo de datos de mercado/macroeconomicos. El frontend en Streamlit presenta resultados interactivos para analisis tecnico, rendimientos, volatilidad, CAPM, VaR/CVaR, optimizacion de portafolio, senales y comparacion contra benchmark.

La solucion utiliza datos dinamicos desde APIs y estandariza validaciones con Pydantic, permitiendo trazabilidad, consistencia y explicabilidad de resultados.

## 3. Activos seleccionados y justificacion
Portafolio sugerido para diversificacion sectorial y geografica:
- NVDA (tecnologia, crecimiento, EEUU)
- BCOLO.CB (financiero, Colombia)
- ECOPETROL.CB (energia, Colombia)
- KO (consumo defensivo, EEUU)
- SPY (benchmark mercado EEUU)

Razon: combinar activos con sensibilidades distintas a ciclos economicos, tasas e inflacion para reducir concentracion de riesgo.

## 4. Metodologia y resultados por modulo
### 4.1 Analisis tecnico
Se implementaron SMA, EMA, RSI, MACD, Bollinger y Estocastico con visualizacion interactiva.
Interpretacion esperada:
- RSI > 70: sobrecompra
- RSI < 30: sobreventa
- Cruce MACD: cambio de impulso

### 4.2 Rendimientos y normalidad
Se calcularon rendimientos simples y logaritmicos, estadisticos descriptivos, histogramas y pruebas Jarque-Bera/Shapiro-Wilk.
Interpretacion esperada: rendimientos financieros suelen mostrar no-normalidad y colas pesadas.

### 4.3 Volatilidad (ARCH/GARCH)
Se compararon ARCH(1), GARCH(1,1) y EGARCH(1,1), seleccionando el mejor por AIC.
Resultado esperado: evidencia de clustering de volatilidad y mejor ajuste de GARCH/EGARCH frente a ARCH basico.

### 4.4 CAPM y beta
Se estimo beta por regresion contra benchmark SPY y se calculo rendimiento esperado CAPM:
E[Ri] = Rf + beta_i (E[Rm] - Rf)

### 4.5 VaR y CVaR
Se calcularon VaR parametrico, historico y Monte Carlo, ademas de CVaR historico.
Interpretacion: CVaR complementa VaR al medir severidad promedio de perdidas extremas.

### 4.6 Markowitz
Se simularon 10,000+ portafolios, construyendo frontera eficiente, portafolio de minima varianza y maximo Sharpe.

### 4.7 Senales de trading
Reglas implementadas: MACD crossover, RSI extremo, Bollinger, cruces sobre media y estocastico.
Salida: senal buy/sell/mixed/neutral por activo con razones explicables.

### 4.8 Macro y benchmark
Se reportan Rf, inflacion y USD/COP. Se compara portafolio vs benchmark con:
- Alpha de Jensen
- Tracking Error
- Information Ratio
- Sharpe
- Max Drawdown

## 5. Arquitectura tecnica
- Backend FastAPI: endpoints para cada modulo de analisis y riesgo.
- Validacion Pydantic: request/response tipados, Field y validadores.
- Dependencias con Depends: configuracion y servicios desacoplados.
- Frontend Streamlit: consumo HTTP del backend en 8 modulos.

## 6. Conclusiones y recomendaciones
- La arquitectura desacoplada mejora mantenibilidad y trazabilidad.
- El uso de metricas complementarias (VaR + CVaR + drawdown + alpha) evita decisiones sesgadas por una sola medida.
- Se recomienda monitoreo periodico y recalibracion de parametros (ventanas, nivel de confianza, universo de activos).

## 7. Limitaciones y trabajo futuro
- Incorporar backtesting Kupiec para validacion estadistica de VaR.
- Integrar costos de transaccion y restricciones reales de rebalanceo.
- Desplegar en nube y automatizar pruebas continuas.
