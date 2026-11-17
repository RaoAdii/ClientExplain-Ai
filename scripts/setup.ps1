$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
if (-not (Test-Path -LiteralPath '.env')) {
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $buffer = New-Object byte[] 32
    $rng.GetBytes($buffer)
    $dbPassword = [BitConverter]::ToString($buffer).Replace('-', '')
    $rng.GetBytes($buffer)
    $devToken = [BitConverter]::ToString($buffer).Replace('-', '')
    $rng.Dispose()
    $content = @"
APP_ENV=development
AUTH_MODE=development
DEV_AUTH_TOKEN=$devToken
POSTGRES_PASSWORD=$dbPassword
DATABASE_URL=postgresql+psycopg://clientexplain:${dbPassword}@127.0.0.1:5432/clientexplain
REDIS_URL=redis://127.0.0.1:6379/0
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
STORAGE_BACKEND=local
PRIVATE_STORAGE_ROOT=.local/private-storage
MAX_UPLOAD_BYTES=26214400
AI_EXTERNAL_PROCESSING_ALLOWED=false
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
IMAGE_PROVIDER=disabled
"@
    [IO.File]::WriteAllText((Join-Path $root '.env'), $content)
}
if (-not (Test-Path -LiteralPath 'apps/web/.env.local')) {
    $tokenLine = Get-Content -LiteralPath '.env' | Where-Object { $_.StartsWith('DEV_AUTH_TOKEN=') }
    $webContent = "NEXT_PUBLIC_SITE_URL=http://localhost:3000`nNEXT_PUBLIC_AUTH_MODE=development`nAPI_INTERNAL_URL=http://127.0.0.1:8000`nAUTH_MODE=development`n$tokenLine`n"
    [IO.File]::WriteAllText((Join-Path $root 'apps/web/.env.local'), $webContent)
}
Write-Host 'Local environment files are ready. Credentials were not printed.'
