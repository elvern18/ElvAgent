"""Dataclasses for GitHub agent."""

from dataclasses import dataclass, field


@dataclass
class PRSnapshot:
    pr_number: int
    head_sha: str
    title: str
    body: str
    author: str
    branch: str
    check_runs: list[dict] = field(default_factory=list)

    @property
    def ci_state(self) -> str:
        """Compute CI state from check_runs.

        Priority: secret_fail > lint_fail > test_fail > mixed_fail > pending > all_pass
        """
        if not self.check_runs:
            return "all_pass"

        failed = [cr for cr in self.check_runs if cr.get("conclusion") == "failure"]
        pending = [cr for cr in self.check_runs if cr.get("status") in ("queued", "in_progress")]

        if any("secret" in cr.get("name", "").lower() for cr in failed):
            return "secret_fail"

        if any(
            "lint" in cr.get("name", "").lower() or "ruff" in cr.get("name", "").lower()
            for cr in failed
        ):
            non_lint_failures = [
                cr
                for cr in failed
                if not (
                    "lint" in cr.get("name", "").lower() or "ruff" in cr.get("name", "").lower()
                )
            ]
            if not non_lint_failures:
                return "lint_fail"

        if failed:
            test_failures = [cr for cr in failed if "test" in cr.get("name", "").lower()]
            if test_failures and len(test_failures) == len(failed):
                return "test_fail"
            return "mixed_fail"

        if pending:
            return "pending"

        return "all_pass"

    @property
    def needs_description(self) -> bool:
        """True if body contains the auto-generated sentinel."""
        try:
            from src.config.constants import PR_DESCRIPTION_SENTINEL
        except ImportError:
            PR_DESCRIPTION_SENTINEL = "<!-- auto-generated -->"
        return PR_DESCRIPTION_SENTINEL in (self.body or "")


@dataclass
class PREvent:
    pr_number: int
    head_sha: str
    event_type: str  # "needs_description", "ci_failure", "needs_review"
    snapshot: PRSnapshot


@dataclass
class WorkerResult:
    pr_number: int
    head_sha: str
    event_type: str
    action_taken: str
    success: bool
    error: str | None = None
