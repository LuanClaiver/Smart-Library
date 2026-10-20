#requires -Version 5.1
# Instalador Smart Library v1.0.17 - Windows PowerShell 5.1
$ErrorActionPreference = 'Stop'
$base = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $base
$serviceName = 'SmartLibraryLocal'
$hostExe = Join-Path $base 'Servidor\SmartLibraryServiceHost.exe'
$source = Join-Path $base 'Servidor\SmartLibraryServiceHost.cs'
$pythonFile = Join-Path $base 'Servidor\python-servico.txt'
$installLog = Join-Path $base 'Dados\instalacao-servico.log'
New-Item -ItemType Directory -Force -Path (Join-Path $base 'Dados') | Out-Null

function Log-Instalacao([string]$msg) {
  $line = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' | ' + $msg
  Write-Host $msg
  Add-Content -LiteralPath $installLog -Value $line -Encoding UTF8
}

# Usa ProcessStartInfo para que erros no stderr do Python NAO virem excecoes
# do PowerShell. E precisamente isso que ocultava o Traceback em v1.0.11.
function Testar-Processo([string]$arquivo, [string]$argumentos, [int]$timeoutMs=16000) {
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName=$arquivo
  $psi.Arguments=$argumentos
  $psi.UseShellExecute=$false
  $psi.CreateNoWindow=$true
  $psi.RedirectStandardOutput=$true
  $psi.RedirectStandardError=$true
  $psi.WorkingDirectory=$base
  foreach ($chave in @('PYTHONHOME','PYTHONPATH','PYTHONPLATLIBDIR','PYTHONUSERBASE')) {
    if ($psi.EnvironmentVariables.ContainsKey($chave)) { $psi.EnvironmentVariables.Remove($chave) }
  }
  $p = New-Object System.Diagnostics.Process
  $p.StartInfo=$psi
  try {
    [void]$p.Start()
    $outTask=$p.StandardOutput.ReadToEndAsync()
    $errTask=$p.StandardError.ReadToEndAsync()
    if (-not $p.WaitForExit($timeoutMs)) {
      try { $p.Kill() } catch {}
      return @{ok=$false; output=''; error='Tempo limite excedido'; code=-1}
    }
    $saida=$outTask.GetAwaiter().GetResult().Trim()
    $erro=$errTask.GetAwaiter().GetResult().Trim()
    return @{ok=($p.ExitCode -eq 0);output=$saida;error=$erro;code=$p.ExitCode}
  } catch {
    return @{ok=$false;output='';error=$_.Exception.Message;code=-1}
  } finally { $p.Dispose() }
}

function Obter-Python {
  $probe='import sys, sqlite3, ssl, http.server, ctypes; assert sys.version_info >= (3,10); print(sys.executable)'
  foreach ($entry in @(
    @{nome='py.exe';arg='-3'},
    @{nome='python.exe';arg=''},
    @{nome='python3.exe';arg=''}
  )) {
    $cmd = Get-Command $entry.nome -ErrorAction SilentlyContinue
    if ($null -eq $cmd) { continue }
    $executavel = $cmd.Source
    $args=($entry.arg+' -E -c "'+$probe+'"').Trim()
    $result=Testar-Processo $executavel $args
    if (-not $result.ok) {
      Log-Instalacao ('[PYTHON] ' + $entry.nome + ' rejeitado: ' + ($result.error -replace '\r?\n',' | '))
      continue
    }
    $path = ($result.output -split '\r?\n' | Select-Object -Last 1).Trim()
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
      Log-Instalacao ('[PYTHON] Caminho retornado nao existe: '+$path)
      continue
    }
    $path = (Resolve-Path -LiteralPath $path).Path
    $verify=Testar-Processo $path ('-E -c "'+$probe+'"')
    if ($verify.ok) { return $path }
    Log-Instalacao ('[PYTHON] Instalacao '+$path+' rejeitada: '+($verify.error -replace '\r?\n',' | '))
  }
  # Preserva o caminho validado em uma execucao anterior.
  if (Test-Path -LiteralPath $pythonFile) {
    $old = (Get-Content -LiteralPath $pythonFile -Raw).Trim()
    if (Test-Path -LiteralPath $old -PathType Leaf) {
      $check=Testar-Processo $old ('-E -c "'+$probe+'"')
      if ($check.ok) { return $old }
      Log-Instalacao ('[PYTHON] Caminho anterior falhou: '+($check.error -replace '\r?\n',' | '))
    }
  }
  throw ('Nao foi encontrada uma instalacao Python funcional. O Python precisa ter os modulos padrao sqlite3, ssl e http.server. ' +
         'Instale Python 3.11/3.12/3.13 de python.org (preferencialmente para todos os usuarios), ' +
         'desmarque variaveis PYTHONHOME/PYTHONPATH personalizadas e execute este instalador novamente. ' +
         'Consulte Dados\instalacao-servico.log para ver a falha exata.')
}

try {
  $admin=([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
  if (-not $admin) { throw 'Abra Gerenciar Smart Library.bat como administrador.' }
  if (-not (Test-Path -LiteralPath (Join-Path $base 'Dados\privacidade.json'))) {
    throw 'Senha Admin nao configurada. Abra Gerenciar Smart Library.bat e escolha 7 primeiro.'
  }
  Log-Instalacao '=== Instalacao/atualizacao Smart Library v1.0.17 ==='
  $python=Obter-Python
  Log-Instalacao ('Python validado: '+$python)
  if ($python -match '\\Users\\[^\\]+\\AppData\\') {
    Log-Instalacao '[AVISO] Python no perfil do usuario. Se LocalSystem nao conseguir inicia-lo, instale Python para todos os usuarios.'
  }
  Set-Content -LiteralPath $pythonFile -Value $python -Encoding ASCII

  $existing=Get-Service -Name $serviceName -ErrorAction SilentlyContinue
  if ($existing -and $existing.Status -ne 'Stopped') {
    Log-Instalacao 'Parando servico anterior...'
    & sc.exe stop $serviceName | Out-Host
    try { $existing.WaitForStatus('Stopped',[TimeSpan]::FromSeconds(20)) } catch {
      throw 'O servico anterior nao parou. Feche Servicos (services.msc) e tente novamente.'
    }
  }
  $occupied=@(Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue)
  if ($occupied.Count -gt 0) {
    $owner=($occupied | Select-Object -ExpandProperty OwningProcess -Unique) -join ', '
    throw ('Porta 3000 ocupada pelo PID '+$owner+'. Feche o outro Smart Library antes de instalar.')
  }
  if (-not (Test-Path -LiteralPath $source)) { throw 'Arquivo SmartLibraryServiceHost.cs ausente. Extraia o ZIP completo.' }
  if (Test-Path -LiteralPath $hostExe) { Remove-Item -LiteralPath $hostExe -Force }
  Log-Instalacao 'Compilando inicializador de servico .NET Framework...'
  Add-Type -Path $source -ReferencedAssemblies @('System.dll','System.Core.dll','System.ServiceProcess.dll') `
      -OutputAssembly $hostExe -OutputType ConsoleApplication -ErrorAction Stop
  if (-not (Test-Path -LiteralPath $hostExe)) { throw 'Compilacao nao produziu SmartLibraryServiceHost.exe.' }
  Log-Instalacao 'Inicializador .NET compilado.'

  $quoted='"'+$hostExe+'"'
  if ($existing) {
    Log-Instalacao 'Servico antigo localizado: atualizando em vez de criar novamente.'
    & sc.exe config $serviceName binPath= $quoted start= auto | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'sc config falhou. Veja a saida exibida acima.' }
  } else {
    & sc.exe create $serviceName binPath= $quoted start= auto DisplayName= 'Smart Library - Biblioteca Local' | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'sc create falhou. Veja a saida exibida acima.' }
  }
  & sc.exe description $serviceName 'Smart Library - catalogo local na porta 3000.' | Out-Null
  & sc.exe failure $serviceName reset= 86400 actions= 'restart/60000/restart/60000/none/0' | Out-Null
  Log-Instalacao 'Iniciando servico...'
  & sc.exe start $serviceName | Out-Host
  if ($LASTEXITCODE -ne 0) { throw 'sc start falhou. Rode a opcao A - Diagnosticar Servico e verifique Dados\servico.log.' }
  $okay=$false
  for($i=0;$i -lt 18;$i++) {
    Start-Sleep -Seconds 1
    $status=Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if ($status -and $status.Status -eq 'Running') {
      try {
        $resp=Invoke-WebRequest -Uri 'http://127.0.0.1:3000/api/status' -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) { $okay=$true;break }
      } catch {}
    }
    if ($status -and $status.Status -eq 'Stopped') { break }
  }
  if (-not $okay) { throw 'Servico nao respondeu em http://127.0.0.1:3000/api/status. Veja Dados\servico.log e Dados\instalacao-servico.log.' }
  Log-Instalacao '[SUCESSO] Servico em execucao, porta 3000 respondendo.'
  Write-Host 'Acesse http://127.0.0.1:3000' -ForegroundColor Green
} catch {
  $detalhe=$_.Exception.ToString()
  Write-Host ('[ERRO] '+$detalhe) -ForegroundColor Red
  try { Add-Content -LiteralPath $installLog -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss')+' | ERRO | '+($detalhe -replace '\r?\n',' | ')) -Encoding UTF8 } catch {}
  Write-Host ('Diagnostico salvo em '+$installLog)
  Write-Host 'Os arquivos originais da biblioteca nao foram apagados pelo instalador.'
  exit 1
}
