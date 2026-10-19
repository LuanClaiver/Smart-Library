@echo off
setlocal EnableExtensions DisableDelayedExpansion
title Smart Library - Publicar no GitHub
pushd "%~dp0" || (
  echo [ERRO] Nao foi possivel abrir a pasta dos arquivos de publicacao.
  pause
  exit /b 1
)
echo.
echo ==============================================
echo    SMART LIBRARY - PUBLICAR NO GITHUB
 echo ==============================================
echo.
if not exist "Enviar-ParaGitHub.ps1" (
  echo [ERRO] Enviar-ParaGitHub.ps1 nao encontrado ao lado do BAT.
  popd
  pause
  exit /b 1
)
rem IMPORTANTE: %%CD%% nao termina em barra invertida, evitando aspas incorporadas ao argumento.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%CD%\Enviar-ParaGitHub.ps1" -SourceFolder "%CD%"
set "RET=%ERRORLEVEL%"
if "%RET%"=="0" (
  echo [OK] Operacao concluida.
) else (
  echo [AVISO] O envio nao foi concluido. Confira a mensagem acima.
)
popd
pause
exit /b %RET%
