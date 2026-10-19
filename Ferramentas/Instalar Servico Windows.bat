@echo off
setlocal
cd /d "%~dp0.."
net session >nul 2>&1
if errorlevel 1 (
 powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs -Wait"
 exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Instalar-Servico.ps1"
if errorlevel 1 echo [ERRO] Instalacao falhou. Verifique Dados\servico.log ou rode Diagnosticar Servico.bat.
echo.
pause
