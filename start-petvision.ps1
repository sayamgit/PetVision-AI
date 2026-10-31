param(
    [string]$Python = '',
    [ValidateRange(1024, 65535)][int]$Port = 8000
)
$ErrorActionPreference = 'Stop'
if (-not $Python) {
    $projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    $existingPython = Join-Path $env:USERPROFILE '.virtualenvs\petvision-ai\Scripts\python.exe'
    if (Test-Path -LiteralPath $projectPython) { $Python = $projectPython }
    elseif (Test-Path -LiteralPath $existingPython) { $Python = $existingPython }
    else { $Python = 'python' }
}
Push-Location (Join-Path $PSScriptRoot 'backend')
try {
    & $Python -c 'import django, qrcode, PIL'
    if ($LASTEXITCODE -ne 0) { throw 'Install requirements-app.txt using your Python environment first. See docs/app-setup.md.' }
    & $Python manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) { throw 'Database setup failed.' }
    Write-Host "PetVision: http://127.0.0.1:$Port/ (Ctrl+C to stop)"
    & $Python manage.py runserver "127.0.0.1:$Port" --noreload
} finally {
    Pop-Location
}
