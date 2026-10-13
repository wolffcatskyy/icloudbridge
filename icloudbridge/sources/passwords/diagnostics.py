"""Actionable error categories and trace locations without exception secrets."""

import traceback

import httpx


def safe_failure(exc: Exception) -> str:
    if isinstance(exc, FileExistsError):
        return "Export already exists; choose a new output filename."
    if isinstance(exc, FileNotFoundError):
        return "Input file not found; select a fresh Apple Passwords export."
    if isinstance(exc, ValueError):
        return "Invalid input; check the Apple CSV format and sync options."
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return "Provider authentication or permission failed; check connection settings."
        return f"Provider request failed (HTTP {code}); refresh snapshots before retrying."
    if isinstance(exc, httpx.TransportError):
        return "Provider connection failed; check network and server availability."
    return f"Password sync failed ({type(exc).__name__}); refresh snapshots before retrying."


def log_failure(logger, exc: Exception) -> None:
    # format_exception would include exception text (possibly a password/body/URL).
    frames = traceback.extract_tb(exc.__traceback__)
    locations = "\n".join(f"{f.filename}:{f.lineno} in {f.name}" for f in frames)
    logger.error("%s\n%s", safe_failure(exc), locations)
