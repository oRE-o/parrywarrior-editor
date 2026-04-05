# Legacy Pygame Editor

This folder contains the frozen pygame-based reference editor.

## Structure

- `src/` : legacy application code
- `assets/` : legacy static assets such as `hitsound.wav`
- `data/charts/` : legacy chart samples and local dev output
- `tools/ffmpeg/` : optional bundled ffmpeg binaries
- `packaging/` : PyInstaller spec for the legacy app
- `tests/` : legacy tests/utilities

## Setup

1. `python -m venv .venv`
2. Activate the virtual environment
3. `pip install -r requirements.txt`

## Run

- `python src/main.py`

## Build

1. `pip install pyinstaller`
2. `pyinstaller packaging/main.spec`

## Runtime data

- Dev mode: `data/charts/`
- Packaged build (Windows): `%APPDATA%\python-rhythm-editor\charts`
- Packaged build (Linux/macOS): `~/.local/share/python-rhythm-editor/charts`

## Notes

- Hitsound path: `assets/hitsound.wav`
- `note_parser` default I/O:
  - input: `data/charts/input_chart.json`
  - output: `data/charts/output_chart.json`
- FFmpeg binaries are not stored in the repo. Place them in `tools/ffmpeg/` or ensure ffmpeg is on `PATH`.
