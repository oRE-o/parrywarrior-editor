# New Editor Architecture

## Goal

Build a polished cross-platform editor from documented legacy behavior without repeating the old pygame monolith.

## Current code layout

- `src/new_editor/core/`
  - `models.py`: chart, note, note type, pending long-note state
  - `legacy_json.py`: legacy-compatible chart serialization and parsing
  - `legacy_rules.py`: deterministic timing and placement rules derived from the legacy editor
- `src/new_editor/services/`
  - `session_io.py`: file-based session loading and atomic save behavior
- `src/new_editor/ui/`
  - `main_window.py`: top-level PySide6 window and menu actions
  - `session.py`: UI-facing session state and status messaging
  - `panels.py`: left/center/right/bottom shell panels
  - `styles.py`, `tokens.py`: visual tokens and styling

## Architectural rules

1. Core rules live outside the UI.
2. File loading/saving lives outside widgets.
3. UI actions call session methods instead of mutating chart data directly.
4. Legacy compatibility is preserved at the chart JSON boundary.
5. Reliability work happens before advanced tooling.

## Near-term milestones

### 1. Foundation

- Keep legacy JSON compatibility stable
- Preserve exact snap / placement / delete rules
- Keep save behavior atomic and recoverable

### 2. Read-only media shell

- Add audio service abstraction
- Add waveform extraction/cache
- Show waveform and time cursor in the new shell
- Add play/pause/stop behavior with clear disabled states until complete

### 3. Editing parity

- Tap placement
- Long-note placement
- Delete behavior with legacy tolerance
- BPM / offset / snap / lane controls
- Note type editing UI

### 4. Reliability UX

- Unsaved-change prompts
- Save result feedback
- Autosave and recovery flow
- Missing song-path warning and repair flow

## Why this split exists

The legacy editor mixed UI, rendering, playback, timing, and editing rules inside `legacy/pygame_editor/src/main.py`. The new editor deliberately separates those responsibilities so future work can improve UI quality and loading/saving stability without breaking legacy behavior accidentally.
