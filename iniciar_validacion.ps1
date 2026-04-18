$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $projectRoot "backend"
$frontendDir = Join-Path $projectRoot "frontend"
$docsDir = Join-Path $projectRoot "docs"
$venvDir = Join-Path $backendDir ".venv312"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$watchdogScript = Join-Path $projectRoot "watchdog_servicios.ps1"

$issueLog = Join-Path $docsDir "incidentes_arranque.md"
$backendLog = Join-Path $docsDir "backend_uvicorn.log"
$backendErrLog = Join-Path $docsDir "backend_uvicorn.err.log"
$frontendLog = Join-Path $docsDir "frontend_http.log"
$frontendErrLog = Join-Path $docsDir "frontend_http.err.log"
$streamlitLog = Join-Path $docsDir "frontend_streamlit.log"
$streamlitErrLog = Join-Path $docsDir "frontend_streamlit.err.log"

if (-not (Test-Path $docsDir)) {
    New-Item -ItemType Directory -Path $docsDir | Out-Null
}

function Write-Step {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK]   $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Register-Issue {
    param(
        [string]$Title,
        [string]$ErrorText,
        [string]$Solution
    )

    if (-not (Test-Path $issueLog)) {
        @(
            "# Incidentes de Arranque",
            "",
            "Registro automatico de errores detectados por iniciar_validacion.ps1.",
            ""
        ) | Set-Content -Path $issueLog -Encoding UTF8
    }

    Add-Content -Path $issueLog -Encoding UTF8 -Value "## $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $Title"
    Add-Content -Path $issueLog -Encoding UTF8 -Value "- Error: $ErrorText"
    Add-Content -Path $issueLog -Encoding UTF8 -Value "- Solucion: $Solution"
    Add-Content -Path $issueLog -Encoding UTF8 -Value ""
}

function Get-CompatiblePython {
    $preferredVersions = @("3.12", "3.11", "3.10")

    foreach ($version in $preferredVersions) {
        try {
            $py = & py -$version -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $py) {
                return @{
                    Version = $version
                    Executable = $py.Trim()
                }
            }
        } catch {
        }
    }

    return $null
}

function Test-Health {
    param([int]$MaxSeconds = 45)

    $deadline = (Get-Date).AddSeconds($MaxSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get -TimeoutSec 3
            if ($resp.status -eq "ok") {
                return $true
            }
        } catch {
        }
        Start-Sleep -Milliseconds 900
    }
    return $false
}

function Test-BackendDependencies {
    try {
        & $venvPython -c "import fastapi,uvicorn,pydantic,pydantic_settings,requests,pandas,numpy,scipy,arch,yfinance; print('ok')" | Out-Null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

function Test-FrontendDependencies {
    param([string]$PythonExe)

    try {
        & $PythonExe -c "import streamlit,plotly,requests,pandas,numpy,scipy; print('ok')" | Out-Null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

try {
    Write-Step "Iniciando watchdog de servicios (auto-reinicio)"
    $watchdogAlreadyRunning = Get-CimInstance Win32_Process |
        Where-Object { $_.Name -match "powershell" -and $_.CommandLine -match "watchdog_servicios.ps1" } |
        Select-Object -First 1

    if (-not $watchdogAlreadyRunning) {
        Start-Process -FilePath "powershell" `
            -ArgumentList "-ExecutionPolicy", "Bypass", "-File", "`"$watchdogScript`"" `
            -WorkingDirectory $projectRoot `
            -WindowStyle Minimized | Out-Null
        Start-Sleep -Seconds 2
        Write-Ok "Watchdog iniciado"
    }
    else {
        Write-Ok "Watchdog ya estaba en ejecucion"
    }

    Write-Step "Validando Python compatible (3.12/3.11/3.10)"
    $pythonInfo = Get-CompatiblePython
    if (-not $pythonInfo) {
        $msg = "No se encontro Python compatible via launcher 'py' (3.12/3.11/3.10)."
        Register-Issue -Title "Python compatible no disponible" -ErrorText $msg -Solution "Instalar Python 3.10+ y volver a ejecutar este script."
        throw $msg
    }
    $pythonExe = $pythonInfo.Executable
    Write-Ok "Python $($pythonInfo.Version) detectado en $pythonExe"

    Write-Step "Preparando entorno virtual backend (.venv312)"
    if (-not (Test-Path $venvPython)) {
        & $pythonExe -m venv $venvDir
        if ($LASTEXITCODE -ne 0) {
            $msg = "No se pudo crear .venv312 en backend."
            Register-Issue -Title "Fallo creando entorno virtual" -ErrorText $msg -Solution "Verificar permisos de escritura en la carpeta backend."
            throw $msg
        }
    }
    Write-Ok "Entorno virtual disponible"

    if (-not (Test-BackendDependencies)) {
        Write-Step "Instalando dependencias backend (primera ejecucion o entorno incompleto)"
        & $venvPython -m pip install --upgrade pip | Out-Null
        & $venvPython -m pip install -r (Join-Path $backendDir "requirements.txt") | Out-Null
        if ($LASTEXITCODE -ne 0) {
            $msg = "No se pudieron instalar dependencias backend."
            Register-Issue -Title "Fallo de dependencias" -ErrorText $msg -Solution "Revisar conexion a internet y ejecutar de nuevo."
            throw $msg
        }
        if (-not (Test-BackendDependencies)) {
            $msg = "Las dependencias no quedaron operativas tras la instalacion."
            Register-Issue -Title "Dependencias incompletas" -ErrorText $msg -Solution "Borrar backend/.venv312 y reintentar iniciar_validacion.ps1."
            throw $msg
        }
        Write-Ok "Dependencias backend instaladas"
    }
    else {
        Write-Ok "Dependencias backend ya estaban listas"
    }

    if (-not (Test-FrontendDependencies -PythonExe $pythonExe)) {
        Write-Step "Instalando dependencias frontend (streamlit)"
        & $pythonExe -m pip install --upgrade pip | Out-Null
        & $pythonExe -m pip install -r (Join-Path $frontendDir "requirements.txt") | Out-Null
        if ($LASTEXITCODE -ne 0 -or -not (Test-FrontendDependencies -PythonExe $pythonExe)) {
            $msg = "No se pudieron instalar dependencias frontend (streamlit)."
            Register-Issue -Title "Fallo de dependencias frontend" -ErrorText $msg -Solution "Revisar conexion a internet y ejecutar de nuevo."
            throw $msg
        }
        Write-Ok "Dependencias frontend instaladas"
    }
    else {
        Write-Ok "Dependencias frontend ya estaban listas"
    }

    Write-Step "Verificando si backend ya esta activo"
    if (-not (Test-Health -MaxSeconds 2)) {
        Write-Step "Levantando FastAPI en 127.0.0.1:8000"
        Start-Process -FilePath $venvPython `
            -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
            -WorkingDirectory $backendDir `
            -RedirectStandardOutput $backendLog `
            -RedirectStandardError $backendErrLog `
            -WindowStyle Minimized | Out-Null

        if (-not (Test-Health -MaxSeconds 45)) {
            $msg = "FastAPI no respondio en /health tras iniciar."
            Register-Issue -Title "Backend no levanta" -ErrorText $msg -Solution "Revisar docs/backend_uvicorn.log para detalle del traceback."
            throw $msg
        }
    }
    Write-Ok "Backend operativo en http://127.0.0.1:8000"

    Write-Step "Levantando servidor estatico frontend (http.server:5500)"
    $frontendUp = $false
    try {
        $probe = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:5500/validacion_calculos.html" -Method Get -TimeoutSec 3
        if ($probe.StatusCode -eq 200) {
            $frontendUp = $true
        }
    } catch {
    }

    if (-not $frontendUp) {
        Start-Process -FilePath $pythonExe `
            -ArgumentList "-m", "http.server", "5500" `
            -WorkingDirectory $frontendDir `
            -RedirectStandardOutput $frontendLog `
            -RedirectStandardError $frontendErrLog `
            -WindowStyle Minimized | Out-Null

        Start-Sleep -Seconds 1
    }

    try {
        $probe2 = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:5500/validacion_calculos.html" -Method Get -TimeoutSec 5
        if ($probe2.StatusCode -ne 200) {
            $msg = "Frontend no devolvio estado 200."
            Register-Issue -Title "Frontend no disponible" -ErrorText $msg -Solution "Revisar docs/frontend_http.log."
            throw $msg
        }
    } catch {
        $msg = "No fue posible abrir servidor frontend en puerto 5500."
        Register-Issue -Title "Fallo servidor frontend" -ErrorText $msg -Solution "Liberar puerto 5500 o cambiar el puerto en el script."
        throw $msg
    }
    Write-Ok "Frontend operativo en http://127.0.0.1:5500/validacion_calculos.html"

    Write-Step "Levantando Streamlit (http://127.0.0.1:8501)"
    $streamlitUp = $false
    try {
        $stProbe = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8501" -Method Get -TimeoutSec 4
        if ($stProbe.StatusCode -eq 200) {
            $streamlitUp = $true
        }
    }
    catch {
    }

    if (-not $streamlitUp) {
        Start-Process -FilePath $pythonExe `
            -ArgumentList "-m", "streamlit", "run", "app.py", "--server.headless", "true", "--server.address", "127.0.0.1", "--server.port", "8501" `
            -WorkingDirectory $frontendDir `
            -RedirectStandardOutput $streamlitLog `
            -RedirectStandardError $streamlitErrLog `
            -WindowStyle Minimized | Out-Null

        Start-Sleep -Seconds 2
    }

    try {
        $stProbe2 = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8501" -Method Get -TimeoutSec 6
        if ($stProbe2.StatusCode -ne 200) {
            $msg = "Streamlit no devolvio estado 200."
            Register-Issue -Title "Streamlit no disponible" -ErrorText $msg -Solution "Revisar docs/frontend_streamlit.err.log."
            throw $msg
        }
    }
    catch {
        $msg = "No fue posible abrir Streamlit en puerto 8501."
        Register-Issue -Title "Fallo servidor Streamlit" -ErrorText $msg -Solution "Liberar puerto 8501 o cambiar el puerto en el script."
        throw $msg
    }
    Write-Ok "Streamlit operativo en http://127.0.0.1:8501"

    Write-Step "Abriendo Swagger, validador y Streamlit en navegador"
    Start-Process "http://127.0.0.1:8000/docs"
    Start-Process "http://127.0.0.1:5500/validacion_calculos.html"
    Start-Process "http://127.0.0.1:8501"

    Write-Host "" 
    Write-Ok "Arranque completo."
    Write-Host "- Backend:  http://127.0.0.1:8000/health"
    Write-Host "- Swagger:  http://127.0.0.1:8000/docs"
    Write-Host "- Validador: http://127.0.0.1:5500/validacion_calculos.html"
    Write-Host "- Streamlit: http://127.0.0.1:8501"
    Write-Host "- Logs:"
    Write-Host "  * $backendLog"
    Write-Host "  * $backendErrLog"
    Write-Host "  * $frontendLog"
    Write-Host "  * $frontendErrLog"
    Write-Host "  * $streamlitLog"
    Write-Host "  * $streamlitErrLog"
    Write-Host "  * $issueLog"
}
catch {
    Write-Host ""
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Se registro el incidente en: $issueLog" -ForegroundColor Yellow
    exit 1
}
