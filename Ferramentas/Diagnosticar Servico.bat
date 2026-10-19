@echo off
setlocal
cd /d "%~dp0.."
echo ===== STATUS SMART LIBRARY =====
sc.exe query SmartLibraryLocal
echo.
echo ===== REGISTRO DO SERVICO =====
sc.exe qc SmartLibraryLocal
echo.
echo ===== PORTA 3000 =====
netstat -ano | findstr :3000
echo.
echo ===== LOG DE INSTALACAO =====
if exist "Dados\instalacao-servico.log" powershell -NoProfile -Command "Get-Content -LiteralPath 'Dados\instalacao-servico.log' -Tail 35"
if not exist "Dados\instalacao-servico.log" echo Ainda nao ha log de instalacao.
echo.
echo ===== LOG DO SERVICO =====
if exist "Dados\servico.log" powershell -NoProfile -Command "Get-Content -LiteralPath 'Dados\servico.log' -Tail 50"
if not exist "Dados\servico.log" echo O servico ainda nao gerou logs.
echo.
echo ===== ARQUIVOS NECESSARIOS =====
if exist "Servidor\SmartLibraryServiceHost.exe" (echo Host: OK) else (echo Host: AUSENTE)
if exist "Servidor\python-servico.txt" (echo Python configurado: OK) else (echo Python configurado: AUSENTE)
if exist "Dados\privacidade.json" (echo Senha Admin configurada: SIM) else (echo Senha Admin configurada: NAO)
echo.
set "REPORT=Dados\diagnostico-servico.txt"
(
 echo SMART LIBRARY - DIAGNOSTICO
 echo Data: %date% %time%
 echo ==== STATUS ====
 sc.exe query SmartLibraryLocal
 echo ==== CONFIG ====
 sc.exe qc SmartLibraryLocal
 echo ==== PORTA ====
 netstat -ano ^| findstr :3000
 echo ==== ULTIMAS MENSAGENS DA INSTALACAO ====
 if exist "Dados\instalacao-servico.log" powershell -NoProfile -Command "Get-Content -LiteralPath 'Dados\instalacao-servico.log' -Tail 35"
 echo ==== ULTIMAS MENSAGENS DO SERVICO ====
 if exist "Dados\servico.log" powershell -NoProfile -Command "Get-Content -LiteralPath 'Dados\servico.log' -Tail 50"
) > "%REPORT%" 2>&1
echo.
echo Diagnostico salvo em: %CD%\%REPORT%
echo ATENCAO: revise caminhos pessoais antes de compartilhar o diagnostico.
pause
