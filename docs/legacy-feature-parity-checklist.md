# Legacy Feature Parity Checklist

This checklist tracks the minimum behavior the new editor must match before the PySide6 shell is considered functionally trustworthy.

## Core chart model and serialization

- [x] Legacy-compatible chart JSON root fields are modeled.
- [x] Legacy-compatible note type payloads are modeled.
- [x] Legacy-compatible notes use nullable `end_time_ms` for long notes.
- [x] JSON round-tripping is implemented in `src/new_editor/core/legacy_json.py`.
- [x] Missing `note_types` restore legacy defaults.
- [x] Old parser/import flow parity is implemented.

## Editing rules

- [x] Snap duration follows BPM and snap division.
- [x] Snap rounding matches the legacy half-away-from-zero rule.
- [x] Placement blocks a note on the same lane at the same snapped time.
- [x] Placement blocks a note inside an existing long note body on the same lane.
- [x] Long-note placement supports pending start state.
- [x] Long-note finalize swaps reversed endpoints.
- [x] Zero-length long-note finalize collapses to a tap note.
- [x] Delete hit detection uses raw time, lane matching, reversed note order, and tolerance.

## Session reliability

- [x] Loading is separated from UI code.
- [x] Saving is separated from UI code.
- [x] Save writes through a temp file first.
- [x] Save keeps a backup when replacing an existing chart.
- [x] Autosave recovery flow exists.
- [x] Corrupt-file recovery UI exists.
- [x] Missing-song warning/relink messaging exists.

## Shell progress and remaining work

- [x] PySide6 window and panel shell
- [x] legacy source import action
- [ ] timeline rendering
- [ ] waveform rendering
- [x] transport controls shell with explicit disabled-state messaging
- [ ] note type editor UI
- [x] song loading/path-linking flow
- [ ] audio playback service
- [ ] hitsound playback during transport
