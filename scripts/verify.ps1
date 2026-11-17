$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
function Invoke-Checked {
    param([string]$Program, [string[]]$CommandArgs)
    & $Program @CommandArgs
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}
Invoke-Checked '.\.venv\Scripts\ruff.exe' @('check', 'services', 'scripts')
Invoke-Checked '.\.venv\Scripts\ruff.exe' @('format', '--check', 'services', 'scripts')
Invoke-Checked '.\.venv\Scripts\python.exe' @('-m', 'pytest', '-q', '--tb=short')
Invoke-Checked '.\.venv\Scripts\alembic.exe' @('-c', 'services/api/alembic.ini', 'check')
Invoke-Checked 'npm.cmd' @('run', 'lint')
Invoke-Checked 'npm.cmd' @('run', 'typecheck')
Invoke-Checked 'npm.cmd' @('test')
Write-Host 'All lint, type, unit and database checks passed. Run the production build and browser suite separately.'
