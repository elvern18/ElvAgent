"""
Unit tests for GitTool.

Covers:
- _slugify()       : correct slug generation from arbitrary strings
- GitTool.make_slug: first-6-words truncation and slug hygiene
- GitTool.create_branch:
    * happy path (branch created on first attempt)
    * unexpected failure (raises RuntimeError)
    * collision recovery (branch already exists → retry with timestamp suffix)
    * retry failure (raises RuntimeError if the suffixed branch also fails)
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.tools.git_tool import GitTool, _ProcResult, _slugify

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_git_tool() -> GitTool:
    """Return a GitTool with a fake repo path (avoids reading real settings)."""
    tool = GitTool.__new__(GitTool)
    tool._repo = "/fake/repo"
    return tool


def _ok() -> _ProcResult:
    return _ProcResult(returncode=0, stdout="", stderr="")


def _fail(stderr: str) -> _ProcResult:
    return _ProcResult(returncode=1, stdout="", stderr=stderr)


def _already_exists(branch: str) -> _ProcResult:
    return _fail(f"fatal: A branch named '{branch}' already exists.")


# ---------------------------------------------------------------------------
# _slugify
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_lowercases_input(self):
        assert _slugify("Hello World") == "hello-world"

    def test_replaces_non_alphanumeric_with_hyphens(self):
        assert _slugify("fix: the/bug") == "fix-the-bug"

    def test_strips_leading_and_trailing_hyphens(self):
        assert _slugify("  hello  ") == "hello"

    def test_respects_max_len(self):
        result = _slugify("a" * 50, max_len=10)
        assert len(result) <= 10

    def test_trailing_hyphen_removed_after_truncation(self):
        # "hello world" → "hello-world" but truncated at 5 → "hello"
        result = _slugify("hello world", max_len=5)
        assert not result.endswith("-")

    def test_collapses_multiple_separators(self):
        assert _slugify("a  --  b") == "a-b"


# ---------------------------------------------------------------------------
# GitTool.make_slug
# ---------------------------------------------------------------------------


class TestMakeSlug:
    def test_uses_first_six_words(self):
        slug = GitTool.make_slug("one two three four five six seven eight")
        assert slug == "one-two-three-four-five-six"

    def test_shorter_instruction_uses_all_words(self):
        assert GitTool.make_slug("fix the bug") == "fix-the-bug"

    def test_raw_instruction_produces_clean_slug(self):
        # "fix the bug in auth module" — all 6 words included
        slug = GitTool.make_slug("fix the bug in auth module")
        assert slug == "fix-the-bug-in-auth-module"

    def test_enriched_instruction_pollutes_slug(self):
        """Documents why task_label must be the raw user instruction.

        When CodeHandler prepends 'Working repository: /home/...' to the
        instruction, make_slug picks up the path fragments and produces a
        misleading branch name.  This test pins that behaviour so any change
        to make_slug() that accidentally regresses it is caught.
        """
        enriched = "Working repository: /home/elvern\n\nfix the bug"
        slug = GitTool.make_slug(enriched)
        # The slug is polluted — this is the bug that task_label was added to fix.
        assert slug != "fix-the-bug"
        assert "working" in slug or "home" in slug

    def test_result_never_exceeds_40_chars(self):
        long = "word " * 20
        assert len(GitTool.make_slug(long)) <= 40


# ---------------------------------------------------------------------------
# GitTool.create_branch
# ---------------------------------------------------------------------------


class TestCreateBranch:
    async def test_returns_branch_name_on_success(self):
        tool = _make_git_tool()
        with patch("src.tools.git_tool._run_proc", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = _ok()
            branch = await tool.create_branch("fix-the-bug")

        assert branch == "pa/fix-the-bug"

    async def test_raises_on_unexpected_git_failure(self):
        tool = _make_git_tool()
        with patch("src.tools.git_tool._run_proc", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = _fail("some other git error")
            with pytest.raises(RuntimeError, match="git checkout -b"):
                await tool.create_branch("fix-the-bug")

    async def test_retries_with_timestamp_suffix_when_branch_already_exists(self):
        """When the first checkout fails with 'already exists', a second attempt
        is made with a 6-digit timestamp appended to the slug."""
        tool = _make_git_tool()
        with (
            patch(
                "src.tools.git_tool._run_proc",
                new_callable=AsyncMock,
                side_effect=[_already_exists("pa/fix-the-bug"), _ok()],
            ) as mock_run,
            patch("src.tools.git_tool.time") as mock_time,
        ):
            mock_time.time.return_value = 1_234_567_890
            branch = await tool.create_branch("fix-the-bug")

        suffix = str(1_234_567_890)[-6:]
        assert branch == f"pa/fix-the-bug-{suffix}"
        # Exactly two git calls were made
        assert mock_run.call_count == 2

    async def test_suffix_truncates_slug_to_keep_total_within_40_chars(self):
        """The slug is truncated to 33 chars before adding '-XXXXXX' (7 chars)
        so the final slug never exceeds 40 chars."""
        tool = _make_git_tool()
        long_slug = "a" * 40  # max allowed slug length

        with (
            patch(
                "src.tools.git_tool._run_proc",
                new_callable=AsyncMock,
                side_effect=[_already_exists(f"pa/{long_slug}"), _ok()],
            ),
            patch("src.tools.git_tool.time") as mock_time,
        ):
            mock_time.time.return_value = 1_234_567_890
            branch = await tool.create_branch(long_slug)

        slug_part = branch.removeprefix("pa/")
        assert len(slug_part) <= 40

    async def test_raises_if_retry_also_fails(self):
        """If both the initial attempt and the suffixed retry fail, RuntimeError
        is raised (avoids an infinite retry loop)."""
        tool = _make_git_tool()
        exists_err = _already_exists("pa/fix-the-bug")
        with (
            patch(
                "src.tools.git_tool._run_proc",
                new_callable=AsyncMock,
                side_effect=[exists_err, _fail("another error")],
            ),
            patch("src.tools.git_tool.time"),
        ):
            with pytest.raises(RuntimeError, match="git checkout -b"):
                await tool.create_branch("fix-the-bug")

    async def test_first_checkout_uses_plain_slug(self):
        """The first git call always uses the unmodified slug."""
        tool = _make_git_tool()
        with patch("src.tools.git_tool._run_proc", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = _ok()
            await tool.create_branch("my-feature")

        first_call_args = mock_run.call_args_list[0]
        assert "pa/my-feature" in first_call_args.args
