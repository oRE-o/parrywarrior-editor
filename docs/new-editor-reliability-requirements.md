# New Editor Reliability Requirements

## Goal

The new editor must treat load/save reliability as a first-class feature. Beginner users should not lose work because of partial writes, opaque errors, or silent format drift.

## Required behaviors for the initial scaffold

1. **Legacy chart compatibility stays stable**
   - The new non-UI core reads and writes the same chart JSON shape documented in `docs/legacy-editor-analysis.md`.
   - Supported root fields are:
     - `song_path`
     - `bpm`
     - `offset_ms`
     - `num_lanes`
     - `note_types`
     - `notes`
   - `note_types` remain keyed by name.
   - `notes` keep `time_ms`, `note_type_name`, `lane`, and nullable `end_time_ms`.

2. **Save behavior must be safer than the legacy implementation**
   - Never write directly into the destination file first.
   - Write the full JSON payload to a temp file in the same directory.
   - Flush and fsync before replacement.
   - Replace the destination atomically with `os.replace`.
   - If a destination file already exists, copy it to a `.bak` file before replacement.
   - Dirty sessions with a known source/save path should write a separate autosave sidecar instead of mutating the main chart file.

3. **Loading should fail loudly and specifically**
   - Invalid root types, note arrays, note type payloads, or malformed colors should raise clear exceptions.
   - The UI shell can translate these exceptions into beginner-friendly dialogs later, but the core should preserve the real cause.

4. **Legacy source import must stay grounded in the frozen parser behavior**
   - Support importing the legacy source format handled by `legacy/pygame_editor/src/note_parser.py`.
   - Map `AudioFilePath`, `Bpm`, `AudioOffset`, `LaneCount`, and `Notes` into the current chart model.
   - Scan `NormalNoteTools`, `AttackNoteTools`, and `TriggerNoteTools` into `note_types`.
   - Convert `Time` seconds to `time_ms` and `AudioOffset` seconds to `offset_ms`.
   - Infer `is_long_note` from tool `Type != 0`.
   - Keep imported `end_time_ms` values as `null` because the legacy parser does not recover hold endpoints.

5. **Core editing rules must stay deterministic and testable**
   - Snap rounding uses the legacy half-away-from-zero rule.
   - Placement checks use snapped time and lane occupancy.
   - Delete checks use raw unsnapped time with tolerance.
   - Long-note finalization reorders backward endpoints and collapses zero-length holds into taps.

6. **No silent data invention beyond documented legacy defaults**
   - Missing `note_types` fall back to legacy defaults (`Tap`, `Long`) because the legacy loader does that today.
   - Other fields may use documented defaults, but the code should not silently reshape arbitrary invalid payloads.

## Shell responsibilities in the current scaffold

The PySide6 shell now already provides file dialogs, unsaved-change prompts, and error dialogs. It should also provide:

- clear success/failure messaging after save
- “unsaved changes” tracking
- explicit recovery UI for newer autosave sidecars and `.bak` files when loading fails
- dedicated legacy-source import that converts into the current chart model without silently reusing the old source path as the save target
- truthful warnings for broken `song_path` references so users can relink audio instead of guessing why playback is disabled

## Non-goals of this scaffold

- no project-relative audio path migration yet
- no waveform/audio services yet
- no editing dialogs or note-type authoring workflow yet
