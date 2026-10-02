$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$experimentRoot = Join-Path $repoRoot 'experiments/memory_scope_fix_20261002'
$runtimeRoot = Join-Path $experimentRoot '.runtime/pi'
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $experimentRoot 'pi-package.json') -Destination (Join-Path $runtimeRoot 'package.json')
Copy-Item -LiteralPath (Join-Path $experimentRoot 'pi-package-lock.json') -Destination (Join-Path $runtimeRoot 'package-lock.json')
Push-Location $runtimeRoot
try {
    npm ci --ignore-scripts --cache (Join-Path $experimentRoot '.cache/npm')
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
} finally {
    Pop-Location
}
