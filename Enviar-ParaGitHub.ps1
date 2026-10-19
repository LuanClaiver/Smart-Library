param(
    [Parameter(Mandatory = $true)]
    [string]$SourceFolder
)
$ErrorActionPreference = 'Stop'
$repoUrl = 'https://github.com/LuanClaiver/Smart-Library.git'
$repoPage = 'https://github.com/LuanClaiver/Smart-Library'
# Normaliza a pasta para evitar barras/aspas extras recebidas do CMD.
$SourceFolder = $SourceFolder.Trim().Trim('"').Trim("'").TrimEnd('\','/')
if (-not $SourceFolder) { Write-Host '[ERRO] Pasta de origem vazia.' -ForegroundColor Red; exit 1 }
try { $source = (Resolve-Path -LiteralPath $SourceFolder -ErrorAction Stop).Path }
catch { Write-Host "[ERRO] Pasta de origem invalida: $SourceFolder" -ForegroundColor Red; exit 1 }
$work = Join-Path $env:LOCALAPPDATA 'SmartLibrary\GitHubRepo'

function Abort($message) {
    Write-Host "`n[ERRO] $message" -ForegroundColor Red
    exit 1
}
function RunGit([string[]]$GitArgs, [string]$Description) {
    Write-Host "[Git] $Description" -ForegroundColor DarkCyan
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) { throw "Git falhou em: $Description (codigo $LASTEXITCODE)." }
}
try {
    Write-Host "`nSMART LIBRARY - ENVIO AO GITHUB" -ForegroundColor Cyan
    Write-Host "Destino: $repoPage"
    Write-Host "Origem:  $source"
    Write-Host "Clone:   $work`n"

    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
        Abort 'Git nao instalado ou fora do PATH. Instale Git for Windows em https://git-scm.com/download/win e abra o BAT novamente.'
    }
    foreach ($p in @('Servidor\server.py','Interface\index.html','README.md','.gitignore')) {
        if (-not (Test-Path -LiteralPath (Join-Path $source $p) -PathType Leaf)) {
            Abort "Execute o BAT dentro da pasta GitHub do projeto. Faltando: $p"
        }
    }

    # Never publish the user's live database or private-data folder.
    $allowedFiles = @(
        '.editorconfig','.gitattributes','.gitignore',
        'Abrir Smart Library.bat','Gerenciar Smart Library.bat',
        'README.md','SECURITY.md','CONTRIBUTING.md',
        'PUBLICAR-NO-GITHUB.md','Enviar para GitHub.bat','Enviar-ParaGitHub.ps1'
    )
    $allowedDirs = @('.github','Documentacao','Ferramentas','Interface','Servidor','tests')
    $allowedData = @('Dados/LEIA-ME.txt','Dados/area_privada.exemplo.json')
    $sensitivePattern = '(?i)(?:^|[\\/])(?:\.git|\.venv|venv|__pycache__|Miniaturas)(?:[\\/]|$)|(?:^|[\\/])\.env(?:\.|$)|(?:^|[\\/])(?:area_privada\.json|biblioteca\.db|admin_password\.json|segredo[s]?)$|\.(?:db|sqlite|sqlite3|db-wal|db-shm|key|pem|pfx|p12|log|zip|7z|bak)$'

    $toCopy = New-Object System.Collections.Generic.List[object]
    foreach ($file in $allowedFiles + $allowedData) {
        $full = Join-Path $source $file
        if (Test-Path -LiteralPath $full -PathType Leaf) {
            $toCopy.Add([pscustomobject]@{ Source=$full; Relative=$file })
        }
    }
    foreach ($dir in $allowedDirs) {
        $folder = Join-Path $source $dir
        if (Test-Path -LiteralPath $folder -PathType Container) {
            $all = Get-ChildItem -LiteralPath $folder -Recurse -Force -File
            foreach ($item in $all) {
                $rel = $dir + '\' + $item.FullName.Substring($folder.Length).TrimStart('\','/')
                if ($rel -match $sensitivePattern) { Abort "Arquivo suspeito na pasta publica: $rel" }
                $toCopy.Add([pscustomobject]@{ Source=$item.FullName; Relative=$rel })
            }
        }
    }
    Write-Host "Arquivos permitidos para publicacao: $($toCopy.Count)" -ForegroundColor Gray
    Write-Host 'A pasta Dados privada NAO sera copiada.' -ForegroundColor Yellow

    $parent = Split-Path -Parent $work
    if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    if (-not (Test-Path -LiteralPath (Join-Path $work '.git') -PathType Container)) {
        if (Test-Path -LiteralPath $work) {
            if ((Get-ChildItem -LiteralPath $work -Force | Measure-Object).Count -gt 0) {
                Abort "O destino $work ja contem arquivos, mas nao e um clone Git. Renomeie a pasta e tente novamente."
            }
        }
        RunGit @('clone',$repoUrl,$work) 'Clonar repositório existente'
    }
    $origin = (& git -C $work remote get-url origin)
    if ($LASTEXITCODE -ne 0 -or ($origin.TrimEnd('/') -ne $repoUrl.TrimEnd('/'))) {
        Abort "A copia local aponta para outro repositorio: $origin"
    }
    # Never reset or force push: preserve any remote changes.
    $existingChanges = & git -C $work status --porcelain
    if ($LASTEXITCODE -ne 0) { Abort 'Falha ao consultar Git status.' }
    if ($existingChanges) { Abort "A copia de trabalho ja contem alteracoes pendentes em $work. Resolva-as antes de continuar." }
    $remoteMain = & git -C $work ls-remote --heads origin main
    if ($LASTEXITCODE -ne 0) { Abort 'Nao foi possivel consultar o GitHub. Verifique Internet e autenticacao.' }
    if ($remoteMain) {
        RunGit @('-C',$work,'fetch','origin','main') 'Buscar atualizacoes remotas'
        $branch = & git -C $work branch --show-current
        if ($branch -ne 'main') { RunGit @('-C',$work,'switch','main') 'Selecionar main' }
        RunGit @('-C',$work,'pull','--ff-only','origin','main') 'Atualizar clone (sem sobrescrever)' 
    } else {
        & git -C $work symbolic-ref HEAD refs/heads/main
        if ($LASTEXITCODE -ne 0) { Abort 'Falha ao selecionar o branch main.' }
    }

    foreach ($item in $toCopy) {
        $destination = Join-Path $work $item.Relative
        $destinationParent = Split-Path -Parent $destination
        if (-not (Test-Path -LiteralPath $destinationParent)) {
            New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
        }
        Copy-Item -LiteralPath $item.Source -Destination $destination -Force
    }
    # Only public sample data, never local data or caches.
    $gitAddArguments = @('-C',$work,'add','--') + $allowedFiles + $allowedDirs + $allowedData
    RunGit $gitAddArguments 'Preparar arquivos publicos'

    $staged = @(& git -C $work -c core.quotepath=false diff --cached --name-only)
    if ($LASTEXITCODE -ne 0) { Abort 'Falha ao listar arquivos preparados.' }
    foreach ($path in $staged) {
        $clean = $path.Replace('/','\')
        if ($clean -match $sensitivePattern) { Abort "Arquivo sensivel bloqueado: $path" }
        if ($clean -match '(?i)^Dados\\' -and $clean -notin @('Dados\LEIA-ME.txt','Dados\area_privada.exemplo.json')) {
            Abort "Conteudo privado do diretorio Dados bloqueado: $path"
        }
    }
    $hasStaged = $staged.Count -gt 0 -and [bool]$staged[0]
    $localCommit = (& git -C $work rev-parse --verify --quiet HEAD)
    $remoteCommit = if ($remoteMain) { ($remoteMain -split '\s+')[0] } else { '' }
    $hasPendingPush = $localCommit -and ($localCommit -ne $remoteCommit)
    if (-not $hasStaged -and -not $hasPendingPush) {
        Write-Host "`nNada novo para enviar. O GitHub ja esta atualizado." -ForegroundColor Green
        exit 0
    }
    if ($hasStaged) {
        Write-Host "`nARQUIVOS QUE SERAO ENVIADOS:" -ForegroundColor Yellow
        foreach ($path in $staged) { Write-Host "  $path" }
    } else {
        Write-Host "`nHa um commit local aguardando envio de tentativa anterior." -ForegroundColor Yellow
    }
    Write-Host "`nO repositorio GitHub e publico. Nao envie segredos ou dados pessoais." -ForegroundColor Yellow
    $confirm = Read-Host 'Digite PUBLICAR para confirmar (qualquer outra resposta cancela)'
    if ($confirm -cne 'PUBLICAR') {
        Write-Host 'Cancelado. Nenhum arquivo enviado.'
        if ($hasStaged) {
            if ($localCommit) {
                & git -C $work reset --hard HEAD | Out-Null
                & git -C $work clean -fd | Out-Null
            } else {
                Remove-Item -LiteralPath $work -Recurse -Force
            }
        }
        exit 0
    }

    if ($hasStaged) {
    $name = & git -C $work config user.name
    if (-not $name) {
        $name = Read-Host 'Nome para os commits Git'
        if (-not $name) { Abort 'Nome do autor obrigatorio.' }
        RunGit @('-C',$work,'config','user.name',$name) 'Configurar autor'
    }
    $email = & git -C $work config user.email
    if (-not $email) {
        $email = Read-Host 'Email Git (pode ser seu email privado noreply do GitHub)'
        if (-not $email -or $email -notmatch '^\S+@\S+\.\S+$') { Abort 'Email Git invalido.' }
        RunGit @('-C',$work,'config','user.email',$email) 'Configurar email do autor'
    }
    $message = Read-Host 'Descricao da atualizacao [Smart Library atualizado]'
    if ([string]::IsNullOrWhiteSpace($message)) { $message = 'Smart Library atualizado' }
    RunGit @('-C',$work,'commit','-m',$message) 'Criar commit'
    }
    Write-Host "`nAutenticacao do GitHub pode abrir o navegador. Siga as instrucoes do Git Credential Manager." -ForegroundColor Cyan
    RunGit @('-C',$work,'push','-u','origin','main') 'Enviar ao GitHub'
    Write-Host "`nPUBLICADO COM SUCESSO: $repoPage" -ForegroundColor Green
    Start-Process $repoPage | Out-Null
} catch {
    Abort $_.Exception.Message
}
