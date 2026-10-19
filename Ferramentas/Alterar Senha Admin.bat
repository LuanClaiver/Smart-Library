@echo off
setlocal
cd /d "%~dp0.."
set "PYCMD=py -3"
py -3 --version >nul 2>&1
if errorlevel 1 set "PYCMD=python"
%PYCMD% --version >nul 2>&1
if errorlevel 1 (
 echo [ERRO] Python 3 nao encontrado. Instale Python 3.10 ou superior.
 pause
 exit /b 1
)
%PYCMD% "Servidor\admin_password.py"
if errorlevel 1 echo [ERRO] Verifique o Python ou a senha informada.
pause
