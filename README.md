# Proyecto Teoría del Riesgo - API de Análisis Financiero

## Autores
- **Paula Andrea Betancour González**

---

## Descripción del Proyecto

Este proyecto implementa una **API REST para análisis cuantitativo de riesgo financiero** utilizando FastAPI en el backend y Streamlit en el frontend. 

El sistema permite analizar portafolios de activos financieros, calcular métricas de riesgo (VaR, CVaR), estimar volatilidades con modelos GARCH, generar la frontera eficiente de Markowitz, aplicar CAPM y proporcionar alertas técnicas basadas en indicadores.

### Componentes Principales

- **Backend**: FastAPI con cálculos cuantitativos de riesgo financiero
- **Frontend**: Interfaz Streamlit para visualización interactiva
- **Datos**: Fuentes de mercado (yfinance, Yahoo Finance, Alpha Vantage, Finnhub)
- **Indicadores**: Técnicos y estadísticos (SMA, EMA, RSI, MACD, Bandas de Bollinger, Estocástico)
- **Modelos**: VaR paramétrico, histórico, Monte Carlo; GARCH; Frontera eficiente

---

## Requisitos Previos

- Python 3.10+
- pip
- git

---

## Instalación

### 1. Clonar el Repositorio

```bash
git clone https://github.com/PaulBetancour/PROY_TEORIA_APIS.git
cd "Proyecto teoria de riesgo"
```

### 2. Crear Entorno Virtual

**En Windows (PowerShell):**
```powershell
python -m venv backend\.venv
& "backend\.venv\Scripts\Activate.ps1"
```

**En macOS/Linux:**
```bash
python -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependencias

#### Backend

```bash
cd backend
pip install -r requirements.txt
cd ..
```

**Paquetes principales:**
- `fastapi==0.116.1` - Framework web
- `uvicorn==0.35.0` - Servidor ASGI
- `pydantic==2.11.7` - Validación de datos
- `pandas==2.3.1` - Análisis de datos
- `numpy==2.3.2` - Computación numérica
- `scipy==1.16.1` - Algoritmos científicos
- `arch==7.2.0` - Modelos GARCH
- `yfinance==0.2.61` - Datos de mercado
- `python-dotenv==1.1.1` - Variables de entorno
- `requests==2.32.4` - HTTP requests

#### Frontend

```bash
cd frontend
pip install -r requirements.txt
cd ..
```

**Paquetes principales:**
- `streamlit==1.46.1` - Framework frontend
- `plotly==6.2.0` - Gráficos interactivos
- `pandas==2.3.1` - Análisis de datos
- `numpy==2.3.2` - Computación numérica
- `scipy==1.16.1` - Algoritmos científicos

---

## Configuración de Variables de Entorno

Crear archivo `.env` en la raíz del proyecto backend:

```bash
# Configuración general
APP_NAME="Proyecto Teoria del Riesgo API"
APP_VERSION="1.0.0"

# Activos por defecto
DEFAULT_TICKERS="NVDA,CIB,EC,KO,SPY"
DEFAULT_BENCHMARK="SPY"

# Historial de datos (años)
HISTORY_YEARS=5

# Proveedor de datos de mercado (yfinance | yahoo | alpha_vantage | finnhub)
MARKET_DATA_PROVIDER="yfinance"

# API Keys (opcionales, según el proveedor seleccionado)
FRED_API_KEY=""
ALPHA_VANTAGE_API_KEY=""
FINNHUB_API_KEY=""

# Parámetros de riesgo
DEFAULT_CONFIDENCE=0.95
TRADING_DAYS=252
MONTE_CARLO_SIMS=10000

# Indicadores técnicos
SMA_WINDOW=20
EMA_WINDOW=20
RSI_WINDOW=14
BB_WINDOW=20
BB_STD=2.0
STOCH_WINDOW=14

# Timeouts y caché
REQUEST_TIMEOUT_SECONDS=8
PRICES_CACHE_TTL_SECONDS=300
```

### Obtención de API Keys (Opcional)

Si deseas usar proveedores alternativos:

1. **Alpha Vantage**: https://www.alphavantage.co/
   - Registrarse y obtener clave API gratuita
   - Establecer `ALPHA_VANTAGE_API_KEY` en `.env`

2. **Finnhub**: https://finnhub.io/
   - Registrarse y obtener clave API gratuita
   - Establecer `FINNHUB_API_KEY` en `.env`

3. **FRED (Federal Reserve Economic Data)**: https://fred.stlouisfed.org/
   - Registrarse y obtener clave API
   - Establecer `FRED_API_KEY` en `.env`

**Nota**: yfinance es la opción predeterminada y no requiere API key.

---

## Ejecución de la Aplicación

### Iniciar Backend

Desde la carpeta raíz del proyecto:

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Salida esperada:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started server process [12345]
```

**URL de la API**: `http://localhost:8000`

**Documentación interactiva**:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Iniciar Frontend

Desde otra terminal:

```bash
cd frontend
streamlit run app.py
```

**Salida esperada:**
```
You can now view your Streamlit app in your browser.
Local URL: http://localhost:8501
Network URL: http://192.168.x.x:8501
```

Abre automáticamente en `http://localhost:8501`

#### Configurar URL del Backend en el Frontend

En el archivo `frontend/app.py`, verificar que la URL del backend sea correcta:

```python
API_URL = "http://localhost:8000"  # Ajustar si es necesario
```

---

## Documentación de Endpoints

### Health Check

**GET** `/health`

Verifica el estado de la API.

**Respuesta:**
```json
{
  "status": "ok",
  "app": "Proyecto Teoria del Riesgo API",
  "version": "1.0.0"
}
```

---

### Activos Disponibles

**GET** `/activos`

Retorna lista de tickers disponibles por defecto.

**Respuesta:**
```json
["NVDA", "CIB", "EC", "KO", "SPY"]
```

---

### Fuentes de Datos

**GET** `/fuentes`

Retorna información de las fuentes de datos configuradas.

**Respuesta:**
```json
{
  "market_data_provider": "yfinance",
  "configured_api_keys": ["FRED"]
}
```

---

### Precios Históricos

**GET** `/precios/{ticker}`

Obtiene datos OHLCV (Open, High, Low, Close, Volume) históricos.

**Parámetros:**
- `ticker` (path): Símbolo del activo (ej: "NVDA")
- `start_date` (query): Fecha inicio (YYYY-MM-DD, opcional)
- `end_date` (query): Fecha fin (YYYY-MM-DD, opcional)

**Ejemplo:**
```
GET /precios/NVDA?start_date=2023-01-01&end_date=2024-01-01
```

**Respuesta:**
```json
{
  "ticker": "NVDA",
  "start_date": "2023-01-01",
  "end_date": "2024-01-01",
  "points": [
    {
      "date": "2023-01-01",
      "open": 130.25,
      "high": 132.50,
      "low": 129.80,
      "close": 131.45,
      "volume": 45000000
    }
  ]
}
```

---

### Rendimientos

**GET** `/rendimientos/{ticker}`

Calcula rendimientos simples y logarítmicos con estadísticas descriptivas.

**Parámetros:**
- `ticker` (path): Símbolo del activo
- `start_date` (query): Fecha inicio (opcional)
- `end_date` (query): Fecha fin (opcional)

**Respuesta:**
```json
{
  "ticker": "NVDA",
  "points": [
    {
      "date": "2023-01-02",
      "simple_return": 0.0095,
      "log_return": 0.0095
    }
  ],
  "stats": {
    "mean": 0.0025,
    "std": 0.0185,
    "skewness": -0.35,
    "kurtosis": 2.85,
    "jarque_bera_stat": 15.42,
    "jarque_bera_pvalue": 0.0004
  }
}
```

---

### Indicadores Técnicos

**GET** `/indicadores/{ticker}`

Calcula indicadores técnicos: SMA, EMA, RSI, MACD, Bandas de Bollinger, Estocástico.

**Parámetros:**
- `ticker` (path): Símbolo del activo
- `start_date` (query): Fecha inicio (opcional)
- `end_date` (query): Fecha fin (opcional)

**Respuesta:**
```json
{
  "ticker": "NVDA",
  "points": [
    {
      "date": "2023-01-20",
      "close": 131.45,
      "sma": 130.20,
      "ema": 131.00,
      "rsi": 65.50,
      "macd": 1.25,
      "macd_signal": 1.10,
      "macd_hist": 0.15,
      "bb_upper": 135.50,
      "bb_mid": 130.20,
      "bb_lower": 124.90,
      "stoch_k": 72.30,
      "stoch_d": 70.15
    }
  ]
}
```

---

### Value at Risk (VaR) y Conditional VaR (CVaR)

**POST** `/var`

Calcula VaR y CVaR mediante 3 metodologías: paramétrica, histórica y Monte Carlo.

**Body (JSON):**
```json
{
  "tickers": ["NVDA", "CIB"],
  "weights": [0.60, 0.40],
  "confidence": 0.95
}
```

**Validaciones:**
- La suma de pesos debe ser exactamente 1.0
- Los pesos deben ser no-negativos
- Mínimo 2 activos en el portafolio
- Confianza entre 0.80 y 0.999

**Respuesta:**
```json
{
  "confidence": 0.95,
  "var_parametric_daily": -0.0325,
  "var_parametric_annualized": -0.5150,
  "var_historical_daily": -0.0318,
  "var_historical_annualized": -0.5045,
  "var_monte_carlo_daily": -0.0330,
  "var_monte_carlo_annualized": -0.5240,
  "cvar_historical_daily": -0.0425,
  "monte_carlo_simulations": 10000
}
```

---

### CAPM (Capital Asset Pricing Model)

**GET** `/capm`

Calcula alpha, beta y retorno esperado según CAPM.

**Parámetros:**
- `tickers` (query): Tickers separados por coma (ej: "NVDA,CIB")
- `benchmark` (query): Benchmark (por defecto "SPY")

**Ejemplo:**
```
GET /capm?tickers=NVDA,CIB&benchmark=SPY
```

**Respuesta:**
```json
{
  "benchmark": "SPY",
  "assets": [
    {
      "ticker": "NVDA",
      "beta": 1.45,
      "alpha": 0.0015,
      "expected_return": 0.0295
    },
    {
      "ticker": "CIB",
      "beta": 0.85,
      "alpha": 0.0008,
      "expected_return": 0.0185
    }
  ],
  "risk_free_rate": 0.0425
}
```

---

### Frontera Eficiente (Markowitz)

**POST** `/frontera-eficiente`

Calcula la frontera eficiente de Markowitz.

**Body (JSON):**
```json
{
  "tickers": ["NVDA", "CIB", "EC", "KO"],
  "n_portfolios": 100
}
```

**Respuesta:**
```json
{
  "portfolios": [
    {
      "weight": {"NVDA": 0.10, "CIB": 0.30, "EC": 0.40, "KO": 0.20},
      "expected_return": 0.0185,
      "volatility": 0.180,
      "sharpe": 0.85
    }
  ],
  "min_variance_portfolio": {...},
  "max_sharpe_portfolio": {...}
}
```

---

### Alertas Técnicas

**GET** `/alertas`

Genera alertas basadas en indicadores técnicos.

**Parámetros:**
- `tickers` (query): Tickers separados por coma
- `rsi_overbought` (query): Umbral RSI sobrecomprado (default: 70.0)
- `rsi_oversold` (query): Umbral RSI sobrevendido (default: 30.0)
- `stoch_overbought` (query): Umbral Estocástico sobrecomprado (default: 80.0)
- `stoch_oversold` (query): Umbral Estocástico sobrevendido (default: 20.0)
- `short_ma_window` (query): Media móvil corta (default: 50)
- `long_ma_window` (query): Media móvil larga (default: 200)

**Ejemplo:**
```
GET /alertas?tickers=NVDA,CIB&rsi_overbought=70
```

**Respuesta:**
```json
{
  "alerts": [
    {
      "ticker": "NVDA",
      "type": "RSI",
      "signal": "OVERBOUGHT",
      "value": 75.5,
      "date": "2024-01-15"
    },
    {
      "ticker": "CIB",
      "type": "MOVING_AVERAGE",
      "signal": "BEARISH_CROSSOVER",
      "value": 50.25,
      "date": "2024-01-15"
    }
  ]
}
```

---

### Datos Macroeconómicos

**GET** `/macro`

Obtiene indicadores macroeconómicos (requiere FRED API key).

**Respuesta:**
```json
{
  "risk_free_rate": 0.0425,
  "market_volatility": 0.185,
  "inflation_rate": 0.032,
  "gdp_growth": 0.028,
  "unemployment_rate": 0.038
}
```

---

### Modelos de Volatilidad (GARCH)

**GET** `/volatilidad/{ticker}`

Estima volatilidad con GARCH y proyecta volatilidad futura.

**Parámetros:**
- `ticker` (path): Símbolo del activo
- `start_date` (query): Fecha inicio (opcional)
- `end_date` (query): Fecha fin (opcional)
- `forecast_steps` (query): Pasos a proyectar (default: 20, rango: 5-120)

**Ejemplo:**
```
GET /volatilidad/NVDA?forecast_steps=20
```

**Respuesta:**
```json
{
  "ticker": "NVDA",
  "historical_volatility": 0.185,
  "garch_estimate": 0.182,
  "forecast": [0.183, 0.184, 0.185, ...],
  "confidence_intervals": {
    "lower": [0.165, 0.166, ...],
    "upper": [0.201, 0.202, ...]
  }
}
```

---

## Activos Seleccionados y Justificación

### Tickers Incluidos por Defecto

| Ticker | Empresa | Sector | Justificación |
|--------|---------|--------|---------------|
| **NVDA** | NVIDIA Corporation | Tecnología | Líder en semiconductores y IA; alta volatilidad para análisis; relevancia en temas de riesgo sistémico |
| **CIB** | Credicorp Ltd. | Finanzas | Institución financiera importante; exposición a mercados emergentes; diversificación geográfica |
| **EC** | Ecuacorreos (puede referirse a entidades ecuatorianas) | Servicios/Diversos | Activo regional; estabilidad de mercado local |
| **KO** | The Coca-Cola Company | Bienes de Consumo | Empresa defensiva; bajo beta; menor volatilidad para diversificación |
| **SPY** | SPDR S&P 500 ETF Trust | Índice/Benchmark | Índice de referencia del mercado accionario estadounidense |

### Criterios de Selección

1. **Diversificación por Sector**: Tecnología, Finanzas, Consumo, Índices
2. **Correlaciones Contrastantes**: NVDA y KO tienen correlaciones bajas
3. **Relevancia Académica**: CAPM, Markowitz y VaR funcionan mejor con activos heterogéneos
4. **Disponibilidad de Datos**: Todos tienen históricos completos en yfinance
5. **Liquidez**: Negociados activamente para análisis técnico fiable
6. **Educativo**: Cubren diferentes perfiles de riesgo (alto: NVDA, bajo: KO)

---

## Uso de Herramientas de IA

### Herramientas y Técnicas Aplicadas

Este proyecto utilizó **asistencia de IA** para:

#### 1. **Generación de Código**
- Implementación de funciones de cálculo cuantitativo
- Estructura de modelos Pydantic
- Lógica de validación y manejo de errores

#### 2. **Diseño de Arquitectura**
- Patrón de dependencias en FastAPI
- Separación de responsabilidades (services, models, config)
- Estructura de cache y timeouts

#### 3. **Optimización de Funciones**
- Uso de `@lru_cache` para settings
- Implementación de caching de precios
- Ejecución asincrónica con `asyncio`

#### 4. **Análisis Técnico y Financiero**
- Implementación de indicadores (SMA, EMA, RSI, MACD, Bandas de Bollinger)
- Cálculo de Jacobiano para Markowitz
- Modelos GARCH con librería `arch`
- Three VaR methodologies (Parametric, Historical, Monte Carlo)

#### 5. **Manejo de Fuentes de Datos**
- Integración multi-proveedor (yfinance, Yahoo, Alpha Vantage, Finnhub)
- Implementación de reintentos con exponential backoff
- Normalización de datos de diferentes fuentes

#### 6. **Documentación**
- Docstrings de funciones
- Comentarios explicativos
- Estructura del README

---

## Estructura del Proyecto

```
Proyecto teoria de riesgo/
├── .git/                          # Repositorio git
├── .gitignore                     # Archivos ignorados (*.env, __pycache__, etc.)
├── README.md                      # Este archivo
├── backend/
│   ├── .env                       # Variables de entorno (no versionar)
│   ├── .venv/                     # Entorno virtual
│   ├── requirements.txt           # Dependencias Python
│   └── app/
│       ├── __init__.py
│       ├── main.py                # Endpoints FastAPI
│       ├── models.py              # Modelos Pydantic
│       ├── services.py            # Lógica de cálculo (RiskCalculator)
│       ├── config.py              # Configuración (Settings)
│       └── dependencies.py        # Inyección de dependencias
├── frontend/
│   ├── .env                       # Variables de entorno (no versionar)
│   ├── app.py                     # Aplicación Streamlit
│   └── requirements.txt           # Dependencias Python
├── docs/
│   ├── errores_y_soluciones.md    # Errores comunes y soluciones
│   ├── incidentes_arranque.md     # Documentación de incidentes
│   └── logs/                      # Archivos de log
```

---

## Troubleshooting

### Errores Comunes y Soluciones

Consultar `docs/errores_y_soluciones.md` para:
- Problemas de conexión a data providers
- Errores de CORS
- Problemas de instalación de dependencias
- Configuración de API keys

### Checking de Incidentes

Revisar `docs/incidentes_arranque.md` para detalles sobre:
- Arranques fallidos del backend/frontend
- Timeout issues
- Data provider issues

---

## Notas sobre Performance

- **Cache de Precios**: 5 minutos (configurable en `.env`)
- **Timeout de Requests**: 8 segundos (configurable)
- **Reintentos**: 1 reintento con backoff exponencial (0.2s)
- **Monte Carlo**: 10,000 simulaciones por defecto (configurable)
- **Trading Days**: 252 días por año (configurable)

---

## Licencia

Proyecto académico. Uso libre para fines educativos.

---

## Referencias

### Bibliografía Teórica

1. **Markowitz, H. (1952)**. Portfolio Selection. The Journal of Finance.
2. **Black, F., & Scholes, M. (1973)**. The Pricing of Options and Corporate Liabilities.
3. **Value at Risk (VaR)**: JP Morgan RiskMetrics
4. **CAPM**: Capital Asset Pricing Model - Sharpe, Lintner, Mossin
5. **GARCH Models**: Engle (1982), Bollerslev (1986)

### Librerías Empleadas

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [yfinance](https://github.com/ranaroussi/yfinance)
- [ARCH Package](https://arch.readthedocs.io/) - GARCH models
- [Pandas Documentation](https://pandas.pydata.org/)
- [SciPy Documentation](https://scipy.org/)

---

## Soporte y Contacto

Para preguntas o reportar bugs, abrir un issue en el repositorio:
[GitHub - PROY_TEORIA_APIS](https://github.com/PaulBetancour/PROY_TEORIA_APIS)

---

**Última actualización**: Abril 2024
**Versión**: 1.0.0
