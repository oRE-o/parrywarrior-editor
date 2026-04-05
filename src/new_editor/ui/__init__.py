try:
    from .main_window import EditorMainWindow
except ModuleNotFoundError:
    EditorMainWindow = None

__all__ = ["EditorMainWindow"]
