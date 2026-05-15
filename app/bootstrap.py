"""Application bootstrap entrypoints."""


def run() -> None:
    """Start the desktop UI application.

    Importing the legacy main window module executes the existing tkinter startup
    flow. This preserves behavior while Alldesk.py remains a thin entrypoint.
    """
    import app.ui.main_window  # noqa: F401
