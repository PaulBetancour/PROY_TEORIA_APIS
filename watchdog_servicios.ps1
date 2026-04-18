$ErrorActionPreference = "Continue"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $projectRoot "backend"
$frontendDir = Join-Path $projectRoot "frontend"
$docsDir = Join-Path $projectRoot "docs"

$venvPython = Join-Path (Join-Path $backendDir ".venv312") "Scripts\python.exe"
$backendLog = Join-Path $docsDir "backend_uvicorn.log"
$backendErrLog = Join-Path $docsDir "backend_uvicorn.err.log"
$frontendLog = Join-Path $docsDir "frontend_http.log"
$frontendErrLog = Join-Path $docsDir "frontend_http.err.log"
$streamlitLog = Join-Path $docsDir "frontend_streamlit.log"
$streamlitErrLog = Join-Path $docsDir "frontend_streamlit.err.log"
$issueLog = Join-Path $docsDir "incidentes_arranque.md"

if (-not (Test-Path $docsDir)) {
    New-Item -ItemType Directory -Path $docsDir | Out-Null
}

function Register-Issue {
    param([string]$Title, [string]$ErrorText, [string]$Solution)

    if (-not (Test-Path $issueLog)) {
        @(
            "# Incidentes de Arranque",
            "",
            "Registro automatico de errores detectados por watchdog.",
            ""
        ) | Set-Content -Path $issueLog -Encoding UTF8
    }

    Add-Content -Path $issueLog -Encoding UTF8 -Value "## $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $Title"
    Add-Content -Path $issueLog -Encoding UTF8 -Value "- Error: $ErrorText"
    Add-Content -Path $issueLog -Encoding UTF8 -Value "- Solucion: $Solution"
    Add-Content -Path $issueLog -Encoding UTF8 -Value ""
}

function Test-Url {
    param([string]$Url, [int]$TimeoutSec = 3)

    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Uri $Url -Method Get -TimeoutSec $TimeoutSec
        return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 400)
    }
    catch {
        return $false
    }
}

function Is-BackendProcessRunning {
    try {
        $p = Get-CimInstance Win32_Process |
            Where-Object { $_.Name -match "python" -and $_.CommandLine -match "uvicorn" -and $_.CommandLine -match "app.main:app" } |
            Select-Object -First 1
        return [bool]$p
    }
    catch {
        return $false
    }
}

function Is-FrontendProcessRunning {
    try {
        $p = Get-CimInstance Win32_Process |
            Where-Object { $_.Name -match "python|py" -and $_.CommandLine -match "http.server" -and $_.CommandLine -match "5500" } |
            Select-Object -First 1
        return [bool]$p
    }
    catch {
        return $false
    }
}

function Is-StreamlitProcessRunning {
    try {
        $p = Get-CimInstance Win32_Process |
            Where-Object { $_.Name -match "python|py" -and $_.CommandLine -match "streamlit" -and $_.CommandLine -match "8501" } |
            Select-Object -First 1
        return [bool]$p
    }
    catch {
        return $false
    }
}

function Ensure-BackendDependencies {
    if (-not (Test-Path $venvPython)) {
        $python312 = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
        if (-not $python312) {
            Register-Issue "Python 3.12 no disponible" "No se detecto py -3.12" "Instalar Python 3.12 y reiniciar watchdog."
            return $false
        }
        & $python312.Trim() -m venv (Join-Path $backendDir ".venv312")
        if ($LASTEXITCODE -ne 0) {
            Register-Issue "No se pudo crear .venv312" "Error creando entorno virtual" "Verificar permisos y espacio en disco."
            return $false
        }
    }

    try {
        & $venvPython -c "import fastapi,uvicorn,pydantic,pydantic_settings,requests,pandas,numpy,scipy,arch" | Out-Null
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
    }
    catch {
    }

    & $venvPython -m pip install --upgrade pip | Out-Null
    & $venvPython -m pip install -r (Join-Path $backendDir "requirements.txt") | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Register-Issue "Dependencias backend" "Fallo pip install -r requirements.txt" "Revisar conectividad a internet y logs de pip."
        return $false
    }

    try {
        & $venvPython -c "import fastapi,uvicorn,pydantic,pydantic_settings,requests,pandas,numpy,scipy,arch" | Out-Null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        Register-Issue "Dependencias incompletas" "Import de modulos criticos fallo tras instalacion" "Eliminar .venv312 y reintentar."
        return $false
    }
}

function Ensure-FrontendDependencies {
    try {
        & py -3.12 -c "import streamlit,plotly,requests,pandas,numpy,scipy" | Out-Null
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
    }
    catch {
    }

    & py -3.12 -m pip install --upgrade pip | Out-Null
    & py -3.12 -m pip install -r (Join-Path $frontendDir "requirements.txt") | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Register-Issue "Dependencias frontend" "Fallo pip install de frontend" "Revisar conectividad a internet y logs de pip."
        return $false
    }

    try {
        & py -3.12 -c "import streamlit,plotly,requests,pandas,numpy,scipy" | Out-Null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        Register-Issue "Dependencias frontend incompletas" "Import de modulos frontend fallo tras instalacion" "Verificar requirements de frontend."
        return $false
    }
}

if (-not (Ensure-BackendDependencies)) {
    exit 1
}

if (-not (Ensure-FrontendDependencies)) {
    exit 1
}

while ($true) {
    try {
        if (-not (Test-Url -Url "http://127.0.0.1:8000/health" -TimeoutSec 2)) {
            if (-not (Is-BackendProcessRunning)) {
                Start-Process -FilePath $venvPython `
                    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
                    -WorkingDirectory $backendDir `
                    -RedirectStandardOutput $backendLog `
                    -RedirectStandardError $backendErrLog `
                    -WindowStyle Minimized | Out-Null
            }

            Start-Sleep -Seconds 3
            if (-not (Test-Url -Url "http://127.0.0.1:8000/health" -TimeoutSec 2)) {
                Register-Issue "Backend no responde" "No se pudo levantar /health" "Revisar docs/backend_uvicorn.err.log para traceback."
            }
        }

        if (-not (Test-Url -Url "http://127.0.0.1:5500/validacion_calculos.html" -TimeoutSec 2)) {
            if (-not (Is-FrontendProcessRunning)) {
                Start-Process -FilePath "py" `
                    -ArgumentList "-3.12", "-m", "http.server", "5500" `
                    -WorkingDirectory $frontendDir `
                    -RedirectStandardOutput $frontendLog `
                    -RedirectStandardError $frontendErrLog `
                    -WindowStyle Minimized | Out-Null
            }

            Start-Sleep -Seconds 2
            if (-not (Test-Url -Url "http://127.0.0.1:5500/validacion_calculos.html" -TimeoutSec 2)) {
                Register-Issue "Frontend no responde" "No se pudo levantar servidor http en puerto 5500" "Verificar puerto ocupado y revisar logs frontend."
            }
        }

        if (-not (Test-Url -Url "http://127.0.0.1:8501" -TimeoutSec 3)) {
            if (-not (Is-StreamlitProcessRunning)) {
                Start-Process -FilePath "py" `
                    -ArgumentList "-3.12", "-m", "streamlit", "run", "app.py", "--server.headless", "true", "--server.address", "127.0.0.1", "--server.port", "8501" `
                    -WorkingDirectory $frontendDir `
                    -RedirectStandardOutput $streamlitLog `
                    -RedirectStandardError $streamlitErrLog `
                    -WindowStyle Minimized | Out-Null
            }

            Start-Sleep -Seconds 3
            if (-not (Test-Url -Url "http://127.0.0.1:8501" -TimeoutSec 3)) {
                Register-Issue "Streamlit no responde" "No se pudo levantar Streamlit en puerto 8501" "Verificar puerto ocupado y revisar logs streamlit."
            }
        }
    }
    catch {
        Register-Issue "Excepcion watchdog" $_.Exception.Message "Reiniciar watchdog y revisar script."
    }

    Start-Sleep -Seconds 8
}
