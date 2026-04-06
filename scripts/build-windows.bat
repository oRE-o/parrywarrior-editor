@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0.."
for %%I in ("%ROOT_DIR%") do set "ROOT_DIR=%%~fI"

set "VENV_DIR=%ROOT_DIR%\.venv"
set "DIST_DIR=%ROOT_DIR%\dist\parry-warrior-editor"
set "STAGE_DIR=%ROOT_DIR%\release-artifacts\current\windows"
set "APP_DIR=%STAGE_DIR%\parry-warrior-editor-win64"
set "ZIP_PATH=%STAGE_DIR%\parry-warrior-editor-win64.zip"

set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "PIP_EXE=%VENV_DIR%\Scripts\pip.exe"
set "PYINSTALLER_EXE=%VENV_DIR%\Scripts\pyinstaller.exe"

echo [Windows] Preparing virtual environment
if not exist "%PYTHON_EXE%" (
    py -3 -m venv "%VENV_DIR%"
    if errorlevel 1 goto :error
)

"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 goto :error

"%PIP_EXE%" install -r "%ROOT_DIR%\requirements-dev.txt"
if errorlevel 1 goto :error

echo [Windows] Building PyInstaller bundle
"%PYINSTALLER_EXE%" --noconfirm "%ROOT_DIR%\packaging\new_editor.spec"
if errorlevel 1 goto :error

if not exist "%DIST_DIR%" (
    echo [Windows] ERROR: build output folder was not created: %DIST_DIR%
    exit /b 1
)

echo [Windows] Staging artifact
"%PYTHON_EXE%" -c "import os, shutil; from pathlib import Path; dist = Path(os.environ['DIST_DIR']); stage = Path(os.environ['STAGE_DIR']); app = Path(os.environ['APP_DIR']); zip_path = Path(os.environ['ZIP_PATH']); stage.mkdir(parents=True, exist_ok=True); shutil.rmtree(app, ignore_errors=True); zip_path.unlink(missing_ok=True); shutil.copytree(dist, app); archive = shutil.make_archive(str(zip_path.with_suffix('')), 'zip', root_dir=app, base_dir='.'); print(archive)"
if errorlevel 1 goto :error

echo [Windows] Done
echo Folder : %APP_DIR%
echo Archive: %ZIP_PATH%
exit /b 0

:error
echo [Windows] Build failed.
exit /b 1
