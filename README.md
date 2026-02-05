# Python Rhythm Editor

## Structure
- src/ : application code
- assets/ : static assets (e.g., hitsound)
- data/charts/ : chart data inputs/outputs
- tools/ffmpeg/ : bundled ffmpeg binaries (optional)
- packaging/ : build spec
- tests/ : tests

## Setup
1. python -m venv .venv
2. .venv\Scripts\activate
3. pip install -r requirements.txt

## Run
- python src/main.py

## Notes
- Hitsound path: assets/hitsound.wav
- Chart save/load defaults to data/charts/ (dev) or user data dir (packaged)
- note_parser default I/O:
  - input: data/charts/input_chart.json
  - output: data/charts/output_chart.json
- FFmpeg binaries are not stored in the repo (size limits). Place them in `tools/ffmpeg/` or ensure ffmpeg is on PATH.
- If audio decoding fails for some formats, make sure ffmpeg is on PATH or bundled in `tools/ffmpeg/` (auto-added).

## Build
1. pip install pyinstaller
2. pyinstaller packaging\main.spec

## Runtime Data
- Dev mode: data/charts/
- Packaged build (Windows): %APPDATA%\python-rhythm-editor\charts
- Packaged build (Linux/macOS): ~/.local/share/python-rhythm-editor/charts
