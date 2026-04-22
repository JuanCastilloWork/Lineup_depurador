
# proyect.ps1
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ModulePath = Join-Path $PSScriptRoot "FletBuild.psm1"

if (Test-Path $ModulePath) {
    Import-Module $ModulePath -Force
    Write-Host ">>> Entorno de Flet Activado <<<" -ForegroundColor Magenta
    Write-Host "Comando disponible: " -NoNewline
    Write-Host "Invoke-FletBuild" -ForegroundColor Cyan
} else {
    Write-Error "No se encontró FletBuild.psm1 en esta carpeta."
}
