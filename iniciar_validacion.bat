@echo off
setlocal
cd /d "%~dp0"
set "PS_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "PS_SCRIPT=%~dp0iniciar_validacion.ps1"

if not exist "%PS_EXE%" (
	where pwsh >nul 2>nul
	if errorlevel 1 (
		echo.
		echo [ERROR] No se encontro PowerShell ^(powershell.exe ni pwsh^) en el sistema.
		goto :end
	)
	set "PS_EXE=pwsh"
)

call "%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%"

if errorlevel 1 (
	echo.
	echo [ERROR] Fallo el arranque. Revisa docs\incidentes_arranque.md
) else (
	echo.
	echo [OK] Arranque finalizado correctamente.
)

:end
if /I not "%NO_PAUSE%"=="1" (
	pause
)
endlocal
