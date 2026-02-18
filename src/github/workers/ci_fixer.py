"""CI Fixer worker: autonomously investigates and fixes CI failures.

Strategy (3 tiers):
  Tier 1 - lint_fail:  ruff auto-fix → commit + push.
                        If ruff makes no changes, escalate to Tier 2.
  Tier 2 - test/mixed: investigate (logs + annotations + file contents) →
                        Claude Sonnet → write fixes → commit + push.
  Tier 3 - secret_fail: post comment only. NEVER modify files.

Circuit breaker: count_fix_attempts(pr_number) >= max_fix_attempts → comment + stop.

Iteration is handled naturally by the AgentLoop polling cycle:
  each push creates a new SHA → next cycle triages the new SHA fresh.
"""

import io
import json
import re
import subprocess
import zipfile
from pathlib import Path

import anthropic

from src.core.state_manager import StateManager
from src.github.client import GitHubClient
from src.github.types import PRSnapshot, WorkerResult
from src.utils.logger import get_logger

try:
    from src.config.constants import MAX_DIFF_CHARS, MAX_FIX_ATTEMPTS, MAX_LOG_CHARS
except ImportError:
    MAX_FIX_ATTEMPTS = 3
    MAX_LOG_CHARS = 4_000
    MAX_DIFF_CHARS = 8_000

logger = get_logger("github.workers.ci_fixer")

SONNET_MODEL = "claude-sonnet-4-6"
MAX_ANNOTATIONS = 20  # cap annotations sent to Claude to avoid prompt bloat


class CIFixer:
    def __init__(
        self,
        client: GitHubClient,
        state_manager: StateManager,
        repo_path: Path,
        max_fix_attempts: int = MAX_FIX_ATTEMPTS,
    ) -> None:
        self._client = client
        self._state_manager = state_manager
        self._repo_path = repo_path
        self._max_fix_attempts = max_fix_attempts
        self._anthropic = anthropic.AsyncAnthropic()

    # ------------------------------------------------------------------ #
    # Git helpers                                                          #
    # ------------------------------------------------------------------ #

    def _run_git(self, args: list[str]) -> subprocess.CompletedProcess:
        cmd = ["git"] + args
        return subprocess.run(cmd, cwd=self._repo_path, capture_output=True, text=True, check=True)

    def _commit_and_push(self, branch: str, message: str) -> None:
        """Stage all changes, commit with ElvAgent identity, and push."""
        self._run_git(["add", "-A"])
        self._run_git(
            [
                "-c",
                "user.email=elvagent@noreply",
                "-c",
                "user.name=ElvAgent",
                "commit",
                "-m",
                message,
            ]
        )
        self._run_git(["push", "origin", branch])

    def _has_staged_changes(self) -> bool:
        """Return True if there are changes staged/unstaged after git add -A."""
        self._run_git(["add", "-A"])
        status = self._run_git(["status", "--porcelain"])
        return bool(status.stdout.strip())

    # ------------------------------------------------------------------ #
    # Investigation: logs, annotations, file contents                     #
    # ------------------------------------------------------------------ #

    async def _fetch_failure_log(self, snapshot: PRSnapshot) -> str:
        """Download the CI failure log from the first failed check run.

        Extracts the workflow run_id from the details_url:
          .../actions/runs/12345678/jobs/987654321  →  run_id = 12345678
        """
        failed_runs = [cr for cr in snapshot.check_runs if cr.get("conclusion") == "failure"]
        if not failed_runs:
            return ""

        details_url = failed_runs[0].get("details_url", "")
        if not details_url or "/runs/" not in details_url:
            return ""

        run_id_str = details_url.split("/runs/")[1].split("/")[0]
        try:
            run_id = int(run_id_str)
        except ValueError:
            return ""

        try:
            zip_bytes = await self._client.get_workflow_run_logs(run_id)
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                log_names = zf.namelist()
                if not log_names:
                    return ""
                with zf.open(log_names[0]) as f:
                    log_text = f.read().decode("utf-8", errors="replace")
                    return log_text[-MAX_LOG_CHARS:]
        except Exception as e:
            logger.warning("log_fetch_failed", error=str(e))
            return ""

    async def _fetch_annotations(self, snapshot: PRSnapshot) -> list[dict]:
        """Fetch check annotations from all failed check runs.

        Annotations give Claude the exact file + line of each error,
        which is far more precise than scanning raw log output.
        """
        failed_runs = [cr for cr in snapshot.check_runs if cr.get("conclusion") == "failure"]
        annotations: list[dict] = []
        for cr in failed_runs:
            try:
                anns = await self._client.list_check_annotations(cr["id"])
                annotations.extend(anns)
            except Exception as e:
                logger.warning("annotation_fetch_failed", check_run=cr.get("name"), error=str(e))
        return annotations[:MAX_ANNOTATIONS]

    def _read_affected_files(self, log: str, annotations: list[dict]) -> dict[str, str]:
        """Read local file contents for every file mentioned in errors.

        Sources of file paths (in priority order):
          1. Check annotations (most reliable — GitHub tells us the exact path)
          2. Log lines matching ``path/to/file.py:line:col:`` patterns

        Files are read from the local checkout (branch already checked out
        before this method is called). Total content is capped at MAX_DIFF_CHARS.
        """
        paths: set[str] = set()

        # 1. Annotation paths
        for ann in annotations:
            if ann.get("path"):
                paths.add(ann["path"])

        # 2. Log lines: capture "src/foo.py:12" style references
        for match in re.finditer(r"([\w/.\\-]+\.py):\d+", log):
            candidate = match.group(1)
            # Skip Python stdlib tracebacks (they reference absolute paths like /usr/...)
            if not candidate.startswith("/"):
                paths.add(candidate)

        result: dict[str, str] = {}
        total_chars = 0

        for path in sorted(paths):
            full_path = self._repo_path / path
            if not full_path.is_file():
                continue
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                remaining = MAX_DIFF_CHARS - total_chars
                if len(content) > remaining:
                    content = content[:remaining]
                result[path] = content
                total_chars += len(content)
                if total_chars >= MAX_DIFF_CHARS:
                    break
            except OSError:
                continue

        return result

    # ------------------------------------------------------------------ #
    # Claude prompt                                                        #
    # ------------------------------------------------------------------ #

    async def _ask_claude_for_fix(
        self,
        snapshot: PRSnapshot,
        log: str,
        annotations: list[dict],
        file_contents: dict[str, str],
        attempt_number: int,
        history: list[dict],
    ) -> dict:
        """Ask Claude Sonnet to diagnose the CI failure and suggest file fixes.

        Returns a dict mapping ``filepath → new_content``.
        Returns ``{}`` if Claude cannot determine a fix.
        """
        # --- Build context sections ---

        history_section = ""
        if history:
            lines = [
                f"  - Attempt {i + 1}: {h['action_taken']} (SHA {h['head_sha'][:7]})"
                for i, h in enumerate(history)
            ]
            history_section = "Previous fix attempts on this PR:\n" + "\n".join(lines) + "\n\n"

        annotations_section = ""
        if annotations:
            ann_lines = [
                f"  {a.get('path', '?')}:{a.get('start_line', '?')}: {a.get('message', '')}"
                for a in annotations
            ]
            annotations_section = "Check annotations (exact error locations):\n"
            annotations_section += "\n".join(ann_lines) + "\n\n"

        files_section = ""
        if file_contents:
            parts = [f"=== {path} ===\n{content}" for path, content in file_contents.items()]
            files_section = "Current contents of affected files:\n" + "\n\n".join(parts) + "\n\n"

        prompt = (
            f"A CI pipeline failed for PR #{snapshot.pr_number} ('{snapshot.title}').\n"
            f"This is fix attempt {attempt_number} of {self._max_fix_attempts}.\n\n"
            f"{history_section}"
            f"{annotations_section}"
            f"CI failure log (last {MAX_LOG_CHARS} chars):\n```\n{log}\n```\n\n"
            f"{files_section}"
            "First, briefly diagnose the root cause. Then return a JSON object mapping "
            "filenames to their COMPLETE corrected content (not diffs — full file content).\n"
            "Only include files that need to change.\n"
            'Format: {"path/to/file.py": "full corrected content", ...}\n'
            "If you cannot determine a fix, return an empty object {}.\n"
            "End your response with ONLY the JSON (no markdown fences, no trailing text)."
        )

        response = await self._anthropic.messages.create(
            model=SONNET_MODEL,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()  # type: ignore[union-attr]

        # Strip ```json ... ``` fences if Claude wraps the output
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])

        # Extract the last JSON object in the response
        # (Claude may prefix with a diagnosis paragraph)
        last_brace = text.rfind("{")
        if last_brace > 0:
            text = text[last_brace:]

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("claude_fix_parse_failed", text=text[:200])
            return {}

    # ------------------------------------------------------------------ #
    # Fix tiers                                                            #
    # ------------------------------------------------------------------ #

    async def _fix_lint(self, snapshot: PRSnapshot, attempt_number: int) -> WorkerResult:
        """Tier 1: ruff auto-fix.

        If ruff makes no changes (error isn't auto-fixable), escalates to
        Claude Sonnet (Tier 2) so the loop can still make progress.
        """
        subprocess.run(  # noqa: ASYNC221
            ["python", "-m", "ruff", "check", "--fix", "src/", "tests/"],
            cwd=self._repo_path,
            capture_output=True,
            text=True,
        )
        subprocess.run(  # noqa: ASYNC221
            ["python", "-m", "ruff", "format", "src/", "tests/"],
            cwd=self._repo_path,
            capture_output=True,
            text=True,
        )

        if not self._has_staged_changes():
            # Ruff couldn't auto-fix — escalate to Claude
            logger.info(
                "ruff_no_changes_escalating_to_claude",
                pr=snapshot.pr_number,
                attempt=attempt_number,
            )
            return await self._fix_with_claude(snapshot, attempt_number)

        self._commit_and_push(snapshot.branch, "fix: Auto-fix lint errors (ruff)")
        logger.info("ruff_fix_pushed", pr=snapshot.pr_number)
        return WorkerResult(
            pr_number=snapshot.pr_number,
            head_sha=snapshot.head_sha,
            event_type="ci_failure",
            action_taken="ruff_fix_pushed",
            success=True,
        )

    async def _fix_with_claude(self, snapshot: PRSnapshot, attempt_number: int) -> WorkerResult:
        """Tier 2: full investigation → Claude Sonnet → apply fixes."""
        log = await self._fetch_failure_log(snapshot)
        annotations = await self._fetch_annotations(snapshot)

        # Branch is already checked out — read files directly from local disk
        file_contents = self._read_affected_files(log, annotations)
        history = await self._state_manager.get_fix_history(snapshot.pr_number)

        logger.info(
            "claude_fix_investigating",
            pr=snapshot.pr_number,
            attempt=attempt_number,
            files_read=len(file_contents),
            annotations=len(annotations),
        )

        fixes = await self._ask_claude_for_fix(
            snapshot, log, annotations, file_contents, attempt_number, history
        )

        if not fixes:
            await self._client.post_pr_comment(
                snapshot.pr_number,
                "**ElvAgent CI Fixer**: Could not determine a fix for the CI failure. "
                "Manual review required.",
            )
            return WorkerResult(
                pr_number=snapshot.pr_number,
                head_sha=snapshot.head_sha,
                event_type="ci_failure",
                action_taken="no_fix_found",
                success=True,
            )

        for filepath, content in fixes.items():
            full_path = self._repo_path / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        if not self._has_staged_changes():
            # Claude returned files but they match existing content
            return WorkerResult(
                pr_number=snapshot.pr_number,
                head_sha=snapshot.head_sha,
                event_type="ci_failure",
                action_taken="no_changes_needed",
                success=True,
            )

        self._commit_and_push(snapshot.branch, "fix: AI-suggested CI fix (ElvAgent)")
        logger.info("ai_fix_pushed", pr=snapshot.pr_number, files=list(fixes.keys()))
        return WorkerResult(
            pr_number=snapshot.pr_number,
            head_sha=snapshot.head_sha,
            event_type="ci_failure",
            action_taken="ai_fix_pushed",
            success=True,
        )

    # ------------------------------------------------------------------ #
    # Entry point                                                          #
    # ------------------------------------------------------------------ #

    async def run(self, snapshot: PRSnapshot) -> WorkerResult:
        """Investigate and fix a CI failure.

        Tier 3 (secret_fail) is handled immediately with a comment.
        All other failures attempt a fix, respecting the circuit breaker.
        """
        ci_state = snapshot.ci_state

        # Tier 3: secret — post warning, never modify files
        if ci_state == "secret_fail":
            await self._client.post_pr_comment(
                snapshot.pr_number,
                "**ElvAgent CI Alert**: Secret scanning failure detected. "
                "Please review and remove any committed secrets manually.",
            )
            return WorkerResult(
                pr_number=snapshot.pr_number,
                head_sha=snapshot.head_sha,
                event_type="ci_failure",
                action_taken="secret_alert_posted",
                success=True,
            )

        # Circuit breaker: total fix pushes across all SHAs for this PR
        attempts = await self._state_manager.count_fix_attempts(snapshot.pr_number)
        if attempts >= self._max_fix_attempts:
            await self._client.post_pr_comment(
                snapshot.pr_number,
                f"**ElvAgent CI Fixer**: Reached maximum fix attempts "
                f"({self._max_fix_attempts}). Manual intervention required.",
            )
            return WorkerResult(
                pr_number=snapshot.pr_number,
                head_sha=snapshot.head_sha,
                event_type="ci_failure",
                action_taken="circuit_breaker_triggered",
                success=True,
            )

        attempt_number = attempts + 1  # 1-indexed for display in prompts

        try:
            # Sync to the exact branch HEAD before making any changes
            self._run_git(["fetch", "origin"])
            self._run_git(["checkout", snapshot.branch])
            self._run_git(["reset", "--hard", f"origin/{snapshot.branch}"])

            if ci_state == "lint_fail":
                return await self._fix_lint(snapshot, attempt_number)
            else:
                # test_fail, mixed_fail → go straight to full investigation
                return await self._fix_with_claude(snapshot, attempt_number)

        except subprocess.CalledProcessError as e:
            logger.error("git_operation_failed", pr=snapshot.pr_number, error=e.stderr)
            return WorkerResult(
                pr_number=snapshot.pr_number,
                head_sha=snapshot.head_sha,
                event_type="ci_failure",
                action_taken="git_error",
                success=False,
                error=e.stderr,
            )
        except Exception as e:
            logger.error("ci_fixer_failed", pr=snapshot.pr_number, error=str(e))
            return WorkerResult(
                pr_number=snapshot.pr_number,
                head_sha=snapshot.head_sha,
                event_type="ci_failure",
                action_taken="failed",
                success=False,
                error=str(e),
            )
