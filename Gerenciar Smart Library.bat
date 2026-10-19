@echo off
setlocal
cd /d "%~dp0"
title Smart Library - Central de Controle
:menu
cls
echo ===============================================
echo            SMART LIBRARY v1.0.15
echo ===============================================
echo.
echo  1 - Abrir biblioteca (navegador / modo local)
echo  2 - Instalar Servico Windows
echo  3 - Consultar status do Servico
echo  4 - Iniciar Servico
echo  5 - Parar Servico
echo  6 - Remover Servico Windows
echo  7 - Criar / Alterar senha Admin
echo  8 - Liberar rede local no Firewall
echo  9 - Instalar FFmpeg (opcional)
echo  A - Diagnosticar Servico
echo  0 - Sair
echo.
choice /C 1234567890A /N /M "Escolha: "
if errorlevel 11 goto diagnosticar
if errorlevel 10 goto sair
if errorlevel 9 goto acao9
if errorlevel 8 goto acao8
if errorlevel 7 goto acao7
if errorlevel 6 goto acao6
if errorlevel 5 goto acao5
if errorlevel 4 goto acao4
if errorlevel 3 goto acao3
if errorlevel 2 goto acao2
if errorlevel 1 goto acao1
:acao1
call "%~dp0Abrir Smart Library.bat"
goto menu
:acao2
call "%~dp0Ferramentas\Instalar Servico Windows.bat"
goto menu
:acao3
call "%~dp0Ferramentas\Status Servico Windows.bat"
goto menu
:acao4
call "%~dp0Ferramentas\Iniciar Servico Windows.bat"
goto menu
:acao5
call "%~dp0Ferramentas\Parar Servico Windows.bat"
goto menu
:acao6
call "%~dp0Ferramentas\Remover Servico Windows.bat"
goto menu
:acao7
call "%~dp0Ferramentas\Alterar Senha Admin.bat"
goto menu
:acao8
call "%~dp0Ferramentas\Liberar Acesso Rede Local.bat"
goto menu
:acao9
call "%~dp0Ferramentas\Instalar Miniaturas (Opcional).bat"
goto menu
:diagnosticar
call "%~dp0Ferramentas\Diagnosticar Servico.bat"
goto menu
:sair
endlocal
exit /b 0
