from .session_io import (
    RecoveryPaths,
    SaveResult,
    autosave_chart_file,
    autosave_chart_path_for,
    backup_chart_path_for,
    clear_autosave_file,
    import_legacy_chart_file,
    load_chart_file,
    load_recovery_chart_file,
    recovery_paths_for,
    save_chart_file,
)

try:
    from .media_session import MediaSessionService, WaveformExtractor
except ModuleNotFoundError:
    MediaSessionService = None
    WaveformExtractor = None

__all__ = [
    "MediaSessionService",
    "RecoveryPaths",
    "SaveResult",
    "WaveformExtractor",
    "autosave_chart_file",
    "autosave_chart_path_for",
    "backup_chart_path_for",
    "clear_autosave_file",
    "import_legacy_chart_file",
    "load_chart_file",
    "load_recovery_chart_file",
    "recovery_paths_for",
    "save_chart_file",
]
