@echo off
setlocal
cd /d "%~dp0.."
fltmc >nul 2>&1
if errorlevel 1 (
    echo [INFO] Solicitando permissao de administrador...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs -Wait"
    exit /b %errorlevel%
)
echo ===============================================
echo       SMART LIBRARY - FIREWALL LAN 3000
echo ===============================================
echo Liberando apenas a sub-rede local ^(TCP porta 3000^).
echo.
rem Atualiza somente a regra criada pelo Smart Library; nao modifica outras.
netsh advfirewall firewall delete rule name="Smart Library LAN 3000" >nul 2>&1
netsh advfirewall firewall add rule name="Smart Library LAN 3000" dir=in action=allow protocol=TCP localport=3000 remoteip=localsubnet profile=any
if errorlevel 1 (
    echo.
    echo [ERRO] O Windows nao liberou a porta 3000.
    echo Verifique se o CMD esta como administrador e se a politica de firewall permite regras locais.
    pause
    exit /b 1
)
echo.
echo [OK] Regra adicionada. Configuracao efetiva:
netsh advfirewall firewall show rule name="Smart Library LAN 3000" verbose
if errorlevel 1 (
    echo [ERRO] A regra nao foi localizada apos a criacao.
    pause
    exit /b 1
)
echo.
ipconfig | findstr /C:"IPv4"
echo Acesse http://IP-DO-PC:3000 pelo celular ou TV na MESMA rede local.
echo Nao encaminhe a porta no roteador para a Internet.
pause
endlocal
