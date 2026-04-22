# =============================================================================
# FletBuild.psm1 — Módulo de powershell para dejar atajos para compilar en flet :3
# =============================================================================
# Uso:
#   Import-Module .\FletBuild.psm1
#   Invoke-FletBuild
# =============================================================================

# Config

$script:Config = @{
    AppName  = "Line up app depurator"
    MainFile = "src/main.py"
    DistPath = "dist"
    ExternalData  = @{
        "src/assets" = "dist/assets"
        "README.md"            = "dist"
        "config.example.json"  = "dist"
        "docs"                 = "dist\docs"
        "templates"            = "dist\templates"
        "data" = "dist/data"
    }
}

function Test-Environment {
    Write-Host "Verificando el entorno correcto"

    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw "Python no encontrado. Intalarlo desde python.org"
    }

    try {
        $fletVersion = python -c "import flet; print(flet.__version__)" 2>$null
        
        if ($LASTEXITCODE -ne 0) {
            throw "Flet no está instalado en este entorno."
        }

        Write-Host "Flet detectado correctamente (Versión: $fletVersion)" -ForegroundColor Green
        return $fletVersion
    }
    catch {
        Write-Host "FALLO: Flet no encontrado." -ForegroundColor Red
        Write-Host "Sugerencia: Ejecuta 'pip install flet'" -ForegroundColor Yellow
        exit # O puedes usar 'return $false' dependiendo de cómo quieras manejar el flujo
    }
}

function Build-App {
    Write-Host ""
    Write-Host " Empaquetando '$($script:Config.AppName)'..." -ForegroundColor Cyan
    Write-Host "   Main file : $($script:Config.MainFile)"
    Write-Host ""

    $params = @(
        $script:Config.MainFile
    )
    flet pack @params

    Write-Host ""
    Write-Host " Copiando archivos externos a dist..." -ForegroundColor Cyan

    foreach ($entry in $script:Config.ExternalData.GetEnumerator()) {
        $source      = $entry.Key
        $destination = $entry.Value

        if (-not (Test-Path $source)) {
            Write-Host "   ADVERTENCIA: '$source' no encontrado, saltando." -ForegroundColor Yellow
            continue
        }

        # Si el origen es carpeta, necesitamos -Recurse y asegurarnos que el destino exista
        if (Test-Path $source -PathType Container) {
            New-Item -ItemType Directory -Force -Path $destination | Out-Null
            Copy-Item -Path "$source\*" -Destination $destination -Recurse -Force
            Write-Host "   [DIR]  $source  -->  $destination" -ForegroundColor Gray
        } else {
            # Para archivos sueltos, solo aseguramos que dist/ exista
            New-Item -ItemType Directory -Force -Path $destination | Out-Null
            Copy-Item -Path $source -Destination $destination -Force
            Write-Host "   [FILE] $source  -->  $destination" -ForegroundColor Gray
        }
    }
    
}

function Invoke-FletBuild {
    <#
    .SYNOPSIS
        Compila el proyecto Flet usando la configuración interna del módulo.
    .DESCRIPTION
        Verifica el entorno, ejecuta flet pack con los parámetros configurados
        en $script:Config y reporta el resultado. La configuración no se expone
        al scope externo.
    .EXAMPLE
        Import-Module .\FletBuild.psm1
        Invoke-FletBuild
    #>
 
    try {
        Test-Environment
        Build-App
 
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "Build exitoso. Ejecutable en: dist\$($script:Config.AppName)" -ForegroundColor Green
        } else {
            throw "flet pack terminó con código de error $LASTEXITCODE"
        }
    }
    catch {
        Write-Host ""
        Write-Host "$_" -ForegroundColor Red
        return
    }
}

Export-ModuleMember -Function Invoke-FletBuild
