param([switch]$Browser)
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
Invoke-Checked '.\.venv\Scripts\python.exe' @('scripts/audit_migrations.py')
Invoke-Checked '.\.venv\Scripts\python.exe' @('-m', 'pip', 'check')
Invoke-Checked 'npm.cmd' @('run', 'lint')
Invoke-Checked 'npm.cmd' @('run', 'typecheck')
Invoke-Checked 'npm.cmd' @('test')
Invoke-Checked 'npm.cmd' @('audit', '--omit=dev')
Invoke-Checked 'npm.cmd' @('run', 'build')
if ($Browser) { Invoke-Checked 'npm.cmd' @('run', 'test:e2e') }
Write-Host 'Lint, type, unit, migration, dependency and production build checks passed.'
if (-not $Browser) { Write-Host 'Start the web/API/worker services, then rerun with -Browser for browser checks.' }
