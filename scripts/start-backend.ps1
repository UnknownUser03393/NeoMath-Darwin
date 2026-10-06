param([string]$NeoMathRoot = 'D:\Development\NeoMath', [int]$Port = 8765)
$ErrorActionPreference = 'Stop'
try {
  $health = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
  if ($health.result.server -ne 'neomath-http') { throw 'Port belongs to another service' }
  Write-Host "NeoMath already running on http://127.0.0.1:$Port"
  exit 0
} catch {
  if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $Port is occupied; refusing to start another service."
  }
}
$backendSource = Join-Path $NeoMathRoot 'desktop\src'
if (!(Test-Path -LiteralPath (Join-Path $backendSource 'neomath\server.py'))) { throw "NeoMath backend not found: $backendSource" }
$venvPython = Join-Path $NeoMathRoot 'desktop\.venv\Scripts\python.exe'
$pythonCommand = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { (Get-Command python).Source }
$env:PYTHONPATH = $backendSource + [IO.Path]::PathSeparator + $env:PYTHONPATH
& $pythonCommand -m neomath --serve --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
