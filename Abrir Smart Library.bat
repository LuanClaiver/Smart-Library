@echo off
setlocal
cd /d "%~dp0"
title Smart Library - Abrir

rem Se o servico esta ativo, basta abrir o navegador.
sc.exe query SmartLibraryLocal 2>nul | findstr /C:"RUNNING" >nul
if not errorlevel 1 (
    rem O servico nao pode abrir o Explorer no desktop. Inicia auxiliar interativo.
    if exist "%~dp0Servidor\local_agent.py" (
        where pyw >nul 2>nul
        if not errorlevel 1 (
            start "" pyw -3 "%~dp0Servidor\local_agent.py"
        ) else (
            where pythonw >nul 2>nul
            if not errorlevel 1 start "" pythonw "%~dp0Servidor\local_agent.py"
        )
    )
    start "" "http://127.0.0.1:3000"
    exit /b 0
)

set "PY_CMD="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 set "PY_CMD=py -3"
if not defined PY_CMD (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python"
)
if not defined PY_CMD (
    echo [ERRO] Python 3.10 ou superior nao encontrado.
    echo Instale em https://www.python.org/downloads/windows/
    pause
    exit /b 1
)
if not exist "%~dp0Servidor\server.py" (
    echo [ERRO] Servidor\server.py ausente. Extraia o ZIP completo.
    pause
    exit /b 1
)
if not exist "%~dp0Interface\index.html" (
    echo [ERRO] Interface\index.html ausente. Extraia o ZIP completo.
    pause
    exit /b 1
)
echo Iniciando Smart Library no modo local...
echo O navegador abre automaticamente. Nao execute o index.html isolado.
%PY_CMD% "%~dp0Servidor\server.py"
echo.
echo O servidor foi encerrado. Confira as mensagens acima.
pause
endlocal
