# Checklist de rubrica (18 secciones)

## Arquitectura y backend
- [x] FastAPI con endpoints principales: /activos, /precios/{ticker}, /rendimientos/{ticker}, /indicadores/{ticker}, /var, /capm, /frontera-eficiente, /alertas, /macro.
- [x] Endpoint extra /volatilidad/{ticker} para ARCH/GARCH.
- [x] Pydantic request/response con Field y validator de pesos.
- [x] Depends para servicios y settings.
- [x] BaseSettings con .env.example.
- [x] Rutas async (mediante to_thread para calculos IO/CPU).

## Modulos de analisis
- [x] Modulo 1 tecnico (SMA, EMA, RSI, MACD, Bollinger, Estocastico).
- [x] Modulo 2 rendimientos + JB/Shapiro.
- [x] Modulo 3 ARCH/GARCH + AIC/BIC + forecast.
- [x] Modulo 4 CAPM con Rf de macro API.
- [x] Modulo 5 VaR parametrico, historico, Monte Carlo + CVaR.
- [x] Modulo 6 Frontera eficiente y portafolios optimos.
- [x] Modulo 7 Senales automaticas.
- [x] Modulo 8 Macro + benchmark metricas.

## Frontend y entrega
- [x] Frontend Streamlit en procesos separados del backend.
- [x] Frontend consume backend por HTTP.
- [x] Caching en frontend y macro snapshot cache en backend.
- [x] Manejo de errores API en frontend y backend.
- [x] requirements con versiones fijas.
- [x] .gitignore y .env.example.
- [x] README principal con guia completa.
- [x] Borrador de informe ejecutivo (docs/INFORME_EJECUTIVO.md).
- [x] Guion de sustentacion (docs/GUION_SUSTENTACION.md).

## Pendiente obligatorio de entrega
- [ ] Convertir informe a PDF final (maximo 5 paginas) con nombres y fecha.

## Pendiente para 5.0 final / bonificacion
- [ ] Agregar tests pytest (ideal para bonus).
- [ ] Agregar backtesting Kupiec (bonus).
- [ ] Agregar despliegue en Render/Railway y Docker (bonus).
