"""
Unit tests for FilesystemTool.

Uses tmp_path fixture to create real temporary directories — no mocking needed
for I/O. Path-guard tests verify PermissionError is raised for escapes.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.tools.filesystem_tool import FilesystemTool, _resolve_and_guard

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tool(root: Path) -> FilesystemTool:
    """Return a FilesystemTool whose pa_working_dir is `root`."""
    with patch("src.tools.filesystem_tool.settings") as m:
        m.pa_working_dir = root
        # Instantiate inside the patch so the guard uses `root`
        tool = FilesystemTool()
    return tool, root


# ---------------------------------------------------------------------------
# Path guard (_resolve_and_guard)
# ---------------------------------------------------------------------------


class TestResolveAndGuard:
    def test_path_inside_root_is_allowed(self, tmp_path):
        target = tmp_path / "subdir" / "file.txt"
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            resolved = _resolve_and_guard(target)
        assert resolved == target

    def test_root_itself_is_allowed(self, tmp_path):
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            resolved = _resolve_and_guard(tmp_path)
        assert resolved == tmp_path

    def test_path_outside_root_raises(self, tmp_path):
        outside = tmp_path.parent / "other"
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            with pytest.raises(PermissionError, match="outside allowed root"):
                _resolve_and_guard(outside)

    def test_path_traversal_blocked(self, tmp_path):
        traversal = tmp_path / "a" / ".." / ".." / "etc" / "passwd"
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            with pytest.raises(PermissionError):
                _resolve_and_guard(traversal)

    def test_symlink_target_checked(self, tmp_path):
        # Symlink inside root that points outside root
        outside = tmp_path.parent / "secret.txt"
        outside.write_text("secret")
        link = tmp_path / "evil_link"
        link.symlink_to(outside)
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            with pytest.raises(PermissionError):
                _resolve_and_guard(link)


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------


class TestReadFile:
    def test_reads_existing_file(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("world")
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            tool = FilesystemTool()
            result = tool.read_file(str(f))
        assert result == "world"

    def test_raises_for_missing_file(self, tmp_path):
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            tool = FilesystemTool()
            with pytest.raises(FileNotFoundError):
                tool.read_file(str(tmp_path / "nope.txt"))

    def test_raises_for_directory(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            tool = FilesystemTool()
            with pytest.raises(IsADirectoryError):
                tool.read_file(str(sub))

    def test_raises_for_path_outside_root(self, tmp_path):
        outside = tmp_path.parent / "outside.txt"
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            tool = FilesystemTool()
            with pytest.raises(PermissionError):
                tool.read_file(str(outside))


# ---------------------------------------------------------------------------
# write_file
# ---------------------------------------------------------------------------


class TestWriteFile:
    def test_creates_new_file(self, tmp_path):
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            tool = FilesystemTool()
            result = tool.write_file(str(tmp_path / "out.txt"), "hello")
        assert (tmp_path / "out.txt").read_text() == "hello"
        assert "hello" in result or "Written" in result

    def test_creates_parent_dirs(self, tmp_path):
        target = tmp_path / "a" / "b" / "c.txt"
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            tool = FilesystemTool()
            tool.write_file(str(target), "nested")
        assert target.read_text() == "nested"

    def test_overwrites_existing_file(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("old")
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            tool = FilesystemTool()
            tool.write_file(str(f), "new")
        assert f.read_text() == "new"

    def test_raises_for_path_outside_root(self, tmp_path):
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            tool = FilesystemTool()
            with pytest.raises(PermissionError):
                tool.write_file(str(tmp_path.parent / "evil.txt"), "data")


# ---------------------------------------------------------------------------
# list_dir
# ---------------------------------------------------------------------------


class TestListDir:
    def test_lists_files(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            tool = FilesystemTool()
            result = tool.list_dir(str(tmp_path))
        assert "a.py" in result
        assert "b.py" in result

    def test_dirs_have_trailing_slash(self, tmp_path):
        (tmp_path / "subdir").mkdir()
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            tool = FilesystemTool()
            result = tool.list_dir(str(tmp_path))
        assert "subdir/" in result

    def test_empty_dir_returns_empty_list(self, tmp_path):
        sub = tmp_path / "empty"
        sub.mkdir()
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            tool = FilesystemTool()
            result = tool.list_dir(str(sub))
        assert result == []

    def test_raises_for_nonexistent_dir(self, tmp_path):
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            tool = FilesystemTool()
            with pytest.raises(FileNotFoundError):
                tool.list_dir(str(tmp_path / "nope"))

    def test_raises_for_file_not_dir(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("")
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            tool = FilesystemTool()
            with pytest.raises(NotADirectoryError):
                tool.list_dir(str(f))


# ---------------------------------------------------------------------------
# exists / make_dir
# ---------------------------------------------------------------------------


class TestExistsAndMakeDir:
    def test_exists_true_for_existing_file(self, tmp_path):
        f = tmp_path / "x.txt"
        f.write_text("")
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            tool = FilesystemTool()
            assert tool.exists(str(f)) is True

    def test_exists_false_for_missing_file(self, tmp_path):
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            tool = FilesystemTool()
            assert tool.exists(str(tmp_path / "nope.txt")) is False

    def test_exists_false_for_path_outside_root(self, tmp_path):
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            tool = FilesystemTool()
            assert tool.exists(str(tmp_path.parent / "nope.txt")) is False

    def test_make_dir_creates_nested(self, tmp_path):
        target = tmp_path / "x" / "y"
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            tool = FilesystemTool()
            tool.make_dir(str(target))
        assert target.is_dir()

    def test_make_dir_idempotent(self, tmp_path):
        target = tmp_path / "dir"
        target.mkdir()
        with patch("src.tools.filesystem_tool.settings") as m:
            m.pa_working_dir = tmp_path
            tool = FilesystemTool()
            tool.make_dir(str(target))  # no error
        assert target.is_dir()
