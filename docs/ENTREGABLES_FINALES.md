# Entregables Finales del Proyecto

## 1) Backend FastAPI
Estado: COMPLETADO
- App FastAPI: backend/app/main.py
- Endpoints implementados (>= 7): /activos, /precios/{ticker}, /rendimientos/{ticker}, /indicadores/{ticker}, /var, /capm, /frontera-eficiente, /alertas, /macro.
- Endpoints adicionales: /benchmark y /volatilidad/{ticker}.
- Modelos Pydantic request/response con Field y @field_validator: backend/app/models.py
- Inyeccion de dependencias con Depends: backend/app/dependencies.py
- Configuracion con BaseSettings y .env: backend/app/config.py
- Documentacion automatica Swagger UI: http://127.0.0.1:8000/docs
- Dependencias con versiones fijas: backend/requirements.txt

## 2) Tablero interactivo (frontend)
Estado: COMPLETADO
- Frontend Streamlit: frontend/app.py
- Navegacion por 8 modulos con tabs: analisis tecnico, rendimientos, ARCH/GARCH, CAPM, VaR/CVaR, Markowitz, senales, macro/benchmark.
- Consume backend por HTTP (requests a endpoints de FastAPI), sin logica de negocio pesada en frontend.
- Incluye textos interpretativos en cada modulo y manejo de errores API.
- Dependencias con versiones fijas: frontend/requirements.txt

## 3) Repositorio Git
Estado: COMPLETADO
- Historial de commits significativo en rama main.
- Archivo .gitignore: .gitignore
- Variables de entorno de ejemplo: backend/.env.example
- README principal: README.md

## 4) Informe ejecutivo (PDF maximo 5 paginas)
Estado: EN CIERRE
- Version editable: docs/INFORME_EJECUTIVO.md
- PDF final: docs/INFORME_EJECUTIVO.pdf
- Pendiente humano final: completar nombres y fecha exacta de entrega.

## 5) Sustentacion oral (15-20 min)
Estado: COMPLETADO
- Guion base: docs/GUION_SUSTENTACION.md
- Incluye secuencia de demo en vivo, preguntas tecnicas esperadas y respuestas sugeridas.

## Evidencia de consulta a Yahoo Finance
- Implementada en backend/app/services.py usando yfinance:
	- yf.download(ticker, ...) para precios por activo.
	- yf.download(tickers, ...) para matriz de retornos del portafolio.
	- yf.download("USDCOP=X", ...) para tasa de cambio.
