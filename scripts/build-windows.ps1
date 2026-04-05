$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$VenvDir = Join-Path $RootDir ".venv"
$DistDir = Join-Path $RootDir "dist\parry-warrior-editor"
$StageDir = Join-Path $RootDir "release-artifacts\current\windows"
$AppDir = Join-Path $StageDir "parry-warrior-editor-win64"
$ZipPath = Join-Path $StageDir "parry-warrior-editor-win64.zip"

Write-Host "[Windows] Preparing virtual environment"
if (!(Test-Path $VenvDir)) {
    py -3 -m venv $VenvDir
}

& "$VenvDir\Scripts\python.exe" -m pip install --upgrade pip
& "$VenvDir\Scripts\pip.exe" install -r "$RootDir\requirements-dev.txt"

Write-Host "[Windows] Building PyInstaller bundle"
& "$VenvDir\Scripts\pyinstaller.exe" --noconfirm "$RootDir\packaging\new_editor.spec"

Write-Host "[Windows] Staging artifact"
New-Item -ItemType Directory -Force -Path $StageDir | Out-Null
if (Test-Path $AppDir) { Remove-Item -Recurse -Force $AppDir }
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
Copy-Item -Recurse "$DistDir" $AppDir
Compress-Archive -Path "$AppDir\*" -DestinationPath $ZipPath -Force

Write-Host "[Windows] Done"
Write-Host "Folder : $AppDir"
Write-Host "Archive: $ZipPath"
