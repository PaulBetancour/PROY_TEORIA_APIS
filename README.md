# Proyecto Teoria del Riesgo con APIs

Proyecto integrador para construir un sistema completo de analisis de riesgo financiero:
- Backend FastAPI (motor de calculo y API REST)
- Frontend Streamlit (tablero interactivo)
- Consumo de APIs externas (Yahoo Finance, FRED)
- Modelos de riesgo: indicadores tecnicos, pruebas de normalidad, ARCH/GARCH, CAPM, VaR/CVaR, Markowitz, alertas, macro y benchmark

## Estructura del repositorio

proyecto-riesgo/
- backend/
  - app/
    - main.py
    - models.py
    - services.py
    - dependencies.py
    - config.py
  - requirements.txt
  - .env.example
- frontend/
  - app.py
  - requirements.txt
- docs/
  - FORMULAS_E_INTERPRETACION.md
  - CHECKLIST_RUBRICA.md
- .gitignore
- README.md

## Activos sugeridos
Portafolio recomendado (diversificacion sectorial y geografica):
- Tecnologia EEUU: NVDA o AAPL
- Financiero Colombia: BCOLO.CB
- Energia Colombia: ECOPETROL.CB
- Consumo defensivo EEUU: KO o WMT
- Benchmark: SPY

## Instalacion

1. Crear entorno virtual en raiz del proyecto.
2. Instalar dependencias backend y frontend.

PowerShell:

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt

3. Configurar variables de entorno.

Copy-Item backend/.env.example backend/.env

4. (Opcional) Agregar FRED_API_KEY en backend/.env.

## Ejecucion

### Backend

uvicorn app.main:app --reload --app-dir backend

Documentacion:
- Swagger: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

### Frontend

streamlit run frontend/app.py

## Endpoints principales
- GET /activos
- GET /precios/{ticker}
- GET /rendimientos/{ticker}
- GET /indicadores/{ticker}
- POST /var
- GET /capm
- POST /frontera-eficiente
- GET /alertas
- GET /macro
- GET /volatilidad/{ticker}

## Validaciones y buenas practicas
- Pydantic v2 con Field y @field_validator
- Depends para inyeccion de servicios
- BaseSettings para configuracion
- Type hints en todo el codigo
- Decorador timed para trazabilidad de tiempo de ejecucion
- Manejo de errores HTTP 400/404/503
- Cache en macro y cache en frontend

## Formula e interpretacion
Ver:
- docs/FORMULAS_E_INTERPRETACION.md

## Checklist de cumplimiento
Ver:
- docs/CHECKLIST_RUBRICA.md

## Uso de IA
Este proyecto fue asistido por herramientas de IA para acelerar estructura, documentacion y validaciones. Todas las decisiones tecnicas deben ser entendidas y defendidas por el equipo durante la sustentacion.
