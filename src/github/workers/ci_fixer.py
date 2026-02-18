"""CI Fixer worker: auto-fixes CI failures."""

import io
import json
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

    def _run_git(self, args: list[str]) -> subprocess.CompletedProcess:
        cmd = ["git"] + args
        return subprocess.run(cmd, cwd=self._repo_path, capture_output=True, text=True, check=True)

    async def _fetch_failure_log(self, snapshot: PRSnapshot) -> str:
        """Fetch CI failure logs. Extract run_id from details_url."""
        failed_runs = [cr for cr in snapshot.check_runs if cr.get("conclusion") == "failure"]
        if not failed_runs:
            return ""

        details_url = failed_runs[0].get("details_url", "")
        if not details_url or "/runs/" not in details_url:
            return ""

        # Extract run_id: URL like .../actions/runs/12345678/jobs/987654321
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

    async def _ask_claude_for_fix(self, snapshot: PRSnapshot, log: str) -> dict:
        """Ask Claude Sonnet to suggest file fixes. Returns {filename: new_content}."""
        prompt = (
            f"A CI pipeline failed for PR #{snapshot.pr_number} ('{snapshot.title}').\n\n"
            f"CI failure log (last {MAX_LOG_CHARS} chars):\n```\n{log}\n```\n\n"
            "Analyze the failure and return a JSON object mapping filenames to their "
            "corrected content. Only include files that need to be changed. "
            'Format: {"path/to/file.py": "corrected file content here", ...}\n'
            "If you cannot determine the fix, return an empty object {}.\n"
            "Return ONLY the JSON, no explanation."
        )
        response = await self._anthropic.messages.create(
            model=SONNET_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Strip JSON fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("claude_fix_parse_failed", text=text[:200])
            return {}

    async def run(self, snapshot: PRSnapshot) -> WorkerResult:
        """Fix CI failures using 3-tier strategy."""
        ci_state = snapshot.ci_state

        # Tier 3: secret_fail - post warning, never modify files
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

        # Circuit breaker: check fix attempt count
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

        try:
            # Checkout the PR branch
            self._run_git(["checkout", snapshot.branch])
            self._run_git(["pull", "origin", snapshot.branch])

            if ci_state == "lint_fail":
                return await self._fix_lint(snapshot)
            else:
                # test_fail or mixed_fail -- Tier 2: Claude Sonnet
                return await self._fix_with_claude(snapshot)

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

    async def _fix_lint(self, snapshot: PRSnapshot) -> WorkerResult:
        """Tier 1: ruff auto-fix."""
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
        self._run_git(["add", "-A"])
        status = self._run_git(["status", "--porcelain"])
        if not status.stdout.strip():
            return WorkerResult(
                pr_number=snapshot.pr_number,
                head_sha=snapshot.head_sha,
                event_type="ci_failure",
                action_taken="no_changes_needed",
                success=True,
            )
        self._run_git(
            [
                "-c",
                "user.email=elvagent@noreply",
                "-c",
                "user.name=ElvAgent",
                "commit",
                "-m",
                "fix: Auto-fix lint errors (ruff)",
            ]
        )
        self._run_git(["push", "origin", snapshot.branch])
        logger.info("ruff_fix_pushed", pr=snapshot.pr_number)
        return WorkerResult(
            pr_number=snapshot.pr_number,
            head_sha=snapshot.head_sha,
            event_type="ci_failure",
            action_taken="ruff_fix_pushed",
            success=True,
        )

    async def _fix_with_claude(self, snapshot: PRSnapshot) -> WorkerResult:
        """Tier 2: Claude Sonnet analysis and fix."""
        log = await self._fetch_failure_log(snapshot)
        fixes = await self._ask_claude_for_fix(snapshot, log)

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

        self._run_git(["add", "-A"])
        status = self._run_git(["status", "--porcelain"])
        if not status.stdout.strip():
            return WorkerResult(
                pr_number=snapshot.pr_number,
                head_sha=snapshot.head_sha,
                event_type="ci_failure",
                action_taken="no_changes_needed",
                success=True,
            )
        self._run_git(
            [
                "-c",
                "user.email=elvagent@noreply",
                "-c",
                "user.name=ElvAgent",
                "commit",
                "-m",
                "fix: AI-suggested CI fix (ElvAgent)",
            ]
        )
        self._run_git(["push", "origin", snapshot.branch])
        logger.info("ai_fix_pushed", pr=snapshot.pr_number, files=list(fixes.keys()))
        return WorkerResult(
            pr_number=snapshot.pr_number,
            head_sha=snapshot.head_sha,
            event_type="ci_failure",
            action_taken="ai_fix_pushed",
            success=True,
        )
