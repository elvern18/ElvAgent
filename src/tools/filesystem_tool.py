"""
FilesystemTool — safe file I/O restricted to settings.pa_working_dir.

All paths are resolved with os.path.realpath() before any I/O.
Any path that escapes pa_working_dir raises PermissionError.
"""

import os
from pathlib import Path

from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("tool.filesystem")

# Large files are truncated so they don't blow up LLM context windows.
_MAX_READ_CHARS = 20_000


def _resolve_and_guard(path: str | Path) -> Path:
    """Resolve path and verify it stays within pa_working_dir."""
    resolved = Path(os.path.realpath(Path(path)))
    root = Path(os.path.realpath(settings.pa_working_dir))
    if not str(resolved).startswith(str(root) + os.sep) and resolved != root:
        raise PermissionError(
            f"Path {path!r} resolves to {resolved!r} which is outside allowed root {root!r}"
        )
    return resolved


class FilesystemTool:
    """Read/write/list operations guarded to pa_working_dir."""

    def read_file(self, path: str) -> str:
        """Read and return the contents of a file as UTF-8 text.

        Files larger than _MAX_READ_CHARS are truncated with a notice so the
        LLM doesn't exhaust its context window on a single file read.
        """
        resolved = _resolve_and_guard(path)
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {path!r}")
        if not resolved.is_file():
            raise IsADirectoryError(f"Path is a directory: {path!r}")
        content = resolved.read_text(encoding="utf-8")
        if len(content) > _MAX_READ_CHARS:
            return (
                content[:_MAX_READ_CHARS] + f"\n...[truncated — {len(content):,} chars total,"
                f" showing first {_MAX_READ_CHARS:,}]"
            )
        return content

    def write_file(self, path: str, content: str) -> str:
        """Write UTF-8 text to a file, creating parent directories as needed."""
        resolved = _resolve_and_guard(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        logger.info("filesystem_write", path=str(resolved), chars=len(content))
        return f"Written {len(content)} chars to {resolved}"

    def list_dir(self, path: str) -> list[str]:
        """Return sorted filenames in a directory."""
        resolved = _resolve_and_guard(path)
        if not resolved.exists():
            raise FileNotFoundError(f"Directory not found: {path!r}")
        if not resolved.is_dir():
            raise NotADirectoryError(f"Not a directory: {path!r}")
        entries = sorted(resolved.iterdir(), key=lambda p: (p.is_file(), p.name))
        return [f"{e.name}/" if e.is_dir() else e.name for e in entries]

    def exists(self, path: str) -> bool:
        """Return True if path exists within the allowed root."""
        try:
            return _resolve_and_guard(path).exists()
        except PermissionError:
            return False

    def make_dir(self, path: str) -> str:
        """Create a directory (and parents) within the allowed root."""
        resolved = _resolve_and_guard(path)
        resolved.mkdir(parents=True, exist_ok=True)
        return f"Directory ready: {resolved}"
