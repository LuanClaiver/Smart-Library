@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0.."
title Smart Library - Miniaturas de videos (opcional)
echo.
echo  SMART LIBRARY - INSTALACAO OPCIONAL DO FFMPEG
echo.
echo  O FFmpeg permite gerar miniaturas de MP4, MKV, AVI e outros videos.
echo  O Smart Library continua funcionando sem ele.
echo.
where ffmpeg >nul 2>nul
if not errorlevel 1 (
  echo FFmpeg encontrado no PATH. Nenhuma instalacao necessaria.
  pause
  exit /b 0
)
where winget >nul 2>nul
if errorlevel 1 (
 echo O Gerenciador de Pacotes do Windows ^(winget^) nao esta disponivel.
 echo Instale FFmpeg em https://ffmpeg.org/download.html
 echo ou coloque o executavel ffmpeg.exe na pasta Ferramentas deste projeto.
 pause
 exit /b 1
)
choice /m "Deseja instalar o FFmpeg usando o winget"
if errorlevel 2 exit /b 0
winget install --id Gyan.FFmpeg --exact --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
 echo.
 echo A instalacao nao foi concluida. Veja a mensagem do winget acima.
) else (
 echo.
 echo Instalacao finalizada. Feche e reabra o Smart Library para reconhecer o FFmpeg.
)
pause
endlocal
