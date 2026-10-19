@echo off
setlocal
net session >nul 2>&1
if errorlevel 1 (
 powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs -Wait"
 exit /b
)
echo Parando e removendo SmartLibraryLocal (Dados serao preservados)...
sc.exe stop SmartLibraryLocal >nul 2>&1
sc.exe delete SmartLibraryLocal
echo Se o Windows informar 1072, feche a janela Servicos e tente novamente.
echo Pasta Dados preservada.
pause
