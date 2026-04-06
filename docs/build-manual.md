# Build Manual

## Goal

This guide explains how to build the new Qt-based editor for Windows, macOS, and Linux.

The current recommended packaging path is **PyInstaller onedir** per platform.

The intended release target is: **users should not need to install ffmpeg separately**. Non-WAV waveform extraction should work from the bundled app output.

## Why onedir

For this project, `onedir` is the safer starting point because:

- Qt Multimedia plugins are easier to inspect
- debugging missing plugin issues is much easier
- cross-platform troubleshooting is simpler than `onefile`
- bundled ffmpeg binaries are easier to verify inside the output folder

Build on the target operating system. Do not expect one OS to build release binaries for another OS.

## 1. Common setup

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
```

Windows (`cmd.exe`):

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\pip.exe install -r requirements-dev.txt
```

## 2. Build command

Use the root packaging spec:

```bash
.venv/bin/pyinstaller packaging/new_editor.spec
```

Windows:

```bat
.venv\Scripts\pyinstaller.exe packaging\new_editor.spec
```

If you want a one-command build with artifact staging, use:

- macOS: `scripts/build-macos.sh`
- Windows: `scripts\build-windows.bat`

Expected output folders:

- `build/new_editor/`
- `dist/parry-warrior-editor/`

## 3. Platform notes

### macOS

- Build on macOS.
- Prefer `onedir` while the app is still evolving.
- Test the produced `dist/parry-warrior-editor/` folder directly before signing or notarization.
- If Pretendard font files are bundled later, verify they are included in the packaged resources.

### Windows

- Build on Windows.
- Launch the produced executable from the `dist/parry-warrior-editor/` folder.
- Verify Qt Multimedia playback works on a clean machine before distributing.

### Linux

- Build on Linux.
- Keep the build environment close to the oldest Linux distribution you intend to support.
- Verify multimedia playback and Qt plugin loading on the target distro family.

## 4. What to test after building

After each platform build:

1. Launch the built app.
2. Open a chart JSON file.
3. Save a chart and confirm replacement save still works.
4. Load a WAV file and test playback.
5. Confirm waveform preview appears for WAV.
6. Load a non-WAV file such as MP3 and confirm waveform preview still works without installing ffmpeg separately.
7. Close with unsaved changes and confirm the prompt appears.

## 5. Current build limitations

- The new editor is still under active development.
- Full legacy editing parity is not complete yet.
- Bundled ffmpeg should be tested on each OS build before distribution.

## 6. Recommended release workflow later

When the editor is closer to full parity:

1. keep using `onedir` for stable CI builds
2. add platform-specific signing/notarization
3. add release smoke tests per OS
4. only evaluate `onefile` after Qt Multimedia/plugin handling is fully stable
