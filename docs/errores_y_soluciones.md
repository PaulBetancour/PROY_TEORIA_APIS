# Errores Comunes y Soluciones - Proyecto Teoria de Riesgo

## Arranque recomendado (1 clic)
- Script PowerShell: `iniciar_validacion.ps1`
- Script doble clic: `iniciar_validacion.bat`
- Watchdog de reinicio automatico: `watchdog_servicios.ps1`
- Registro automatico de incidentes: `docs/incidentes_arranque.md`
- Logs tecnicos:
  - `docs/backend_uvicorn.log`
  - `docs/frontend_http.log`

## Nota sobre Yahoo directo vs backend local
- El HTML de validacion usa `http://127.0.0.1:8000` porque el backend es quien consulta Yahoo y aplica calculos (rendimientos, CAPM, VaR, Markowitz).
- Esto evita bloqueos CORS del navegador y centraliza validaciones matematicas en Python.
- Si el backend no esta arriba, aparece `Failed to fetch`; con el watchdog, el servicio se reinicia automaticamente.

## 1) Error en HTML: Failed to fetch
- Sintoma: En el validador aparece `Backend: Failed to fetch`.
- Causa raiz: El backend FastAPI no esta levantado o no responde en `http://127.0.0.1:8000`.
- Solucion:
  1. Ejecutar `iniciar_validacion.ps1` desde la raiz del proyecto.
  2. Verificar `http://127.0.0.1:8000/health`.
- Prevencion: Usar siempre el script de arranque automatico para no olvidar iniciar servicios.

## 2) TypeError: 'type' object is not subscriptable en config.py
- Sintoma: Falla al iniciar backend en `default_tickers: list[str]`.
- Causa raiz: Se ejecuto con Python 3.8; el proyecto requiere Python 3.9+ (recomendado 3.12).
- Solucion:
  1. Instalar Python 3.12.
  2. Crear/usar entorno `.venv312`.
- Prevencion: Mantener el backend siempre con Python 3.12.

## 3) No module named uvicorn / fastapi
- Sintoma: Al iniciar backend, faltan modulos.
- Causa raiz: Dependencias no instaladas en el entorno virtual correcto.
- Solucion:
  1. Activar o usar `.venv312`.
  2. Ejecutar `pip install -r backend/requirements.txt`.
- Prevencion: Ejecutar el script `iniciar_validacion.ps1`, que instala dependencias automaticamente.

## 4) CORS y consultas desde HTML local
- Sintoma: El navegador bloquea peticiones al backend.
- Causa raiz: Configuracion CORS no adecuada.
- Solucion: Backend con middleware CORS habilitado en `backend/app/main.py`.
- Prevencion: Consumir el HTML desde servidor local (`http.server`) y no desde `file://`.

## 5) Puerto ocupado (8000 o 5500)
- Sintoma: No inicia backend o frontend por conflicto de puerto.
- Causa raiz: Otro proceso ya usa ese puerto.
- Solucion:
  1. Cerrar proceso anterior.
  2. O cambiar puerto en el script.
- Prevencion: Reutilizar instancia ya activa o liberar puertos antes de levantar nuevos procesos.
