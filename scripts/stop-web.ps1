$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path.TrimEnd('\')
$servers = Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" | Where-Object {
    $command = [string]$_.CommandLine
    $command = $command.Replace('/', '\')
    $command.Contains($root + '\') -and $command.Contains('\next\') -and $command -match '\s(start|dev)\s'
}
foreach ($server in $servers) { Stop-Process -Id $server.ProcessId -Force }
Write-Host "Stopped $(@($servers).Count) Next.js server(s) belonging to this workspace."
