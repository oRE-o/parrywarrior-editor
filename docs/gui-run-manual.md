# GUI Run Manual

## Goal

This guide explains how to run and manually test the new Qt-based editor shell locally.

## 1. Create the virtual environment

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
```

On Windows PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

## 2. Pretendard font

The new editor prefers **Pretendard**.

- If Pretendard is already installed on your system, the app will use it automatically.
- If you want to bundle local font files later, place them in one of these folders:
  - `assets/fonts/`
  - `legacy/pygame_editor/assets/fonts/`

Supported local file patterns:

- `Pretendard*.otf`
- `Pretendard*.ttf`

## 3. Run the new editor

From the repository root:

```bash
.venv/bin/python src/new_editor/app.py
```

On Windows:

```powershell
.venv\Scripts\python.exe src\new_editor\app.py
```

## 4. Current scope of the GUI

The current new editor already supports:

- opening legacy-compatible chart JSON files
- importing the older source-chart format handled by the frozen legacy parser
- safe chart save / save as
- sidecar autosave recovery for dirty sessions with a known file anchor
- `.bak` backup recovery prompts after corrupt or failed opens
- song path linking
- read-only playback through Qt Multimedia
- waveform preview for PCM WAV files
- left / center / right / bottom editor shell layout

The current new editor does **not** yet support full note editing parity.

## 5. Recommended manual test checklist

### Basic startup

1. Launch the app.
2. Confirm the main window opens.
3. Confirm the layout shows:
   - left waveform overview
   - center timeline workspace
   - right inspector/tools
   - bottom transport

### Chart load/save

1. Open a chart JSON file.
2. Confirm chart metadata appears in the shell.
3. Use **Save As** to write a new file.
4. Save again to the same location.
5. Confirm a `.bak` backup file is created on replacement saves.

### Legacy source import

1. Use **Import legacy source…** on `legacy/pygame_editor/data/charts/input_chart.json`.
2. Confirm the imported chart opens as an unsaved session instead of silently reusing the source file as the save target.
3. Confirm note timing is converted from seconds to milliseconds and note types are created from the legacy tool lists.
4. Confirm **Save As** suggests a normal chart JSON name.

### Autosave + recovery

1. Open or import a chart that has a real file anchor.
2. Make a change and wait for the autosave interval.
3. Confirm a sibling `*.autosave.chart.json` file appears.
4. Reopen the chart and confirm the shell offers the newer autosave snapshot when appropriate.
5. Corrupt the main chart JSON manually, reopen it, and confirm the shell offers available autosave and/or `.bak` recovery files.

### Song link + playback

1. Load a WAV file.
2. Confirm waveform preview appears.
3. Press **Play**.
4. Confirm transport state and current time update.
5. Press **Pause** and **Stop**.

### Non-WAV behavior

1. Load an MP3 or other supported audio file.
2. Confirm playback still works.
3. Confirm the UI explains waveform preview limitations truthfully instead of pretending it exists.

### Missing song path behavior

1. Open a chart whose `song_path` no longer exists.
2. Confirm the shell warns that the linked song is missing on disk.
3. Confirm the editor still opens the chart and invites the user to relink audio with **Load Song…**.

### Unsaved changes

1. Load a song into a chart.
2. Try to open another chart or close the app.
3. Confirm the unsaved-changes prompt appears.

## 6. Automated checks

Run tests:

```bash
.venv/bin/python -m pytest tests/new_editor
```

Compile check:

```bash
.venv/bin/python -m compileall src/new_editor tests/new_editor legacy/pygame_editor/src
```

## 7. Known current limitations

- waveform preview is currently implemented for PCM WAV files only
- full timeline/note editing parity is still in progress
- cross-format waveform decoding will need a later decode/cache layer
