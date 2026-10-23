$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

function Find-Python {
    foreach ($name in @('python', 'py')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        $args = if ($name -eq 'py') { @('-3', '-c', 'import sys; print(sys.version_info >= (3,10))') } else { @('-c', 'import sys; print(sys.version_info >= (3,10))') }
        try { if ((& $cmd.Source @args 2>$null) -eq 'True') { return $cmd.Source } } catch {}
    }
    return $null
}

function Find-Ollama {
    $command = Get-Command ollama -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $candidate = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    return $null
}

function Install-WingetPackage([string]$id) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) { throw 'Windows Package Manager (winget) is unavailable. Install App Installer from Microsoft, then rerun setup.cmd.' }
    & $winget.Source install --id $id --exact --source winget --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "Installation failed for $id (exit code $LASTEXITCODE)." }
}

Write-Host 'Checking Python 3.10+...'
$python = Find-Python
if (-not $python) {
    Install-WingetPackage 'Python.Python.3.12'
    $env:Path += ';' + (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312') + ';' + (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\Scripts')
    $python = Find-Python
    if (-not $python) { throw 'Python was installed but is not on PATH. Open a new terminal and rerun setup.cmd.' }
}
Write-Host "Python ready: $python"

Write-Host 'Checking Ollama...'
$ollama = Find-Ollama
if (-not $ollama) {
    Install-WingetPackage 'Ollama.Ollama'
    $ollama = Find-Ollama
    if (-not $ollama) { throw 'Ollama was installed but was not found. Open a new terminal and rerun setup.cmd.' }
}
Write-Host "Ollama ready: $ollama"

$model = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'config.json') -Raw | ConvertFrom-Json).ollama_model
if ($model -notmatch '^[a-zA-Z0-9._/-]+:[a-zA-Z0-9._-]+$' -or $model.EndsWith(':cloud')) { throw 'config.json contains an invalid or cloud model name.' }
$models = & $ollama list 2>$null
if ($LASTEXITCODE -ne 0) {
    $service = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\Ollama app.exe'
    if (Test-Path -LiteralPath $service) { Start-Process -FilePath $service -WindowStyle Hidden }
    Start-Sleep -Seconds 5
    $models = & $ollama list
    if ($LASTEXITCODE -ne 0) { throw 'Ollama service did not start. Launch Ollama once and rerun setup.cmd.' }
}
if (-not ($models | Select-String -SimpleMatch "$model ")) {
    Write-Host "Downloading local model $model. This can take time and needs several GB of disk space."
    & $ollama pull $model
    if ($LASTEXITCODE -ne 0) { throw "Model download failed. Rerun setup.cmd to resume: $model" }
}
Write-Host "Local model ready: $model"
