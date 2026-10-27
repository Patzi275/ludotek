$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$specFile = Join-Path $projectRoot "ludotek.spec"
$webDirectory = Join-Path $projectRoot "gamelib\web"
$distDirectory = Join-Path $projectRoot "dist"
$executable = Join-Path $distDirectory "Ludotek.exe"

if (-not (Test-Path -LiteralPath $specFile -PathType Leaf)) {
    throw "Fichier de build introuvable : $specFile"
}

foreach ($file in @("index.html", "app.js", "style.css")) {
    $webFile = Join-Path $webDirectory $file
    if (-not (Test-Path -LiteralPath $webFile -PathType Leaf)) {
        throw "Ressource web introuvable : $webFile"
    }
}

$python = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command py.exe -ErrorAction SilentlyContinue
}
if (-not $python) {
    throw "Python est introuvable. Installez Python 3.8 ou une version plus récente."
}

# "Stop" would turn the stderr of a missing module into an exception and hide the message below.
$ErrorActionPreference = "Continue"
$pyinstallerCheck = & $python.Source -m PyInstaller --version 2>$null
$ErrorActionPreference = "Stop"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller est introuvable. Installez-le avec : $($python.Source) -m pip install pyinstaller"
}

Write-Host "Construction de Ludotek.exe avec PyInstaller $pyinstallerCheck..."

$arguments = @(
    "-m", "PyInstaller",
    "--clean",
    "--noconfirm",
    "--distpath", $distDirectory,
    "--workpath", (Join-Path $projectRoot "build"),
    $specFile
)

Push-Location $projectRoot
try {
    & $python.Source @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "La construction PyInstaller a échoué (code $LASTEXITCODE)."
    }
}
finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "L'exécutable attendu n'a pas été créé : $executable"
}

$size = [math]::Round((Get-Item -LiteralPath $executable).Length / 1MB, 2)
Write-Host "Construction terminée : $executable ($size Mo)"

