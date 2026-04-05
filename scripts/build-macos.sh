#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
DIST_DIR="$ROOT_DIR/dist/parry-warrior-editor"
STAGE_DIR="$ROOT_DIR/release-artifacts/current/macos"
APP_DIR="$STAGE_DIR/parry-warrior-editor-macos"
ZIP_PATH="$STAGE_DIR/parry-warrior-editor-macos.zip"

echo "[macOS] Preparing virtual environment"
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
pip install -r "$ROOT_DIR/requirements-dev.txt"

echo "[macOS] Building PyInstaller bundle"
pyinstaller --noconfirm "$ROOT_DIR/packaging/new_editor.spec"

echo "[macOS] Staging artifact"
mkdir -p "$STAGE_DIR"
rm -rf "$APP_DIR" "$ZIP_PATH"
cp -R "$DIST_DIR" "$APP_DIR"

python3 - <<PY
from pathlib import Path
import shutil
app_dir = Path(r"$APP_DIR")
zip_base = app_dir.with_suffix("")
shutil.make_archive(str(zip_base), "zip", root_dir=app_dir.parent, base_dir=app_dir.name)
print(zip_base.with_suffix('.zip'))
PY

echo "[macOS] Done"
echo "Folder : $APP_DIR"
echo "Archive: $ZIP_PATH"
