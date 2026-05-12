"""Runtime environment detection."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Context:
    """Immutable runtime context.

    Works in GitHub Actions and locally. GitHub-specific fields are
    empty strings when not in GA.
    """

    # GitHub context
    commit_sha: str = ""
    workflow_name: str = ""
    job_name: str = ""
    run_id: str = ""
    run_number: str = ""
    repository: str = ""
    actor: str = ""
    branch: str = ""
    event_name: str = ""
    ref: str = ""

    # Derived
    run_url: str = ""
    is_github_actions: bool = False

    # Local context
    is_interactive: bool = False
    step_summary_path: str = ""
    project_root: Path = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        # frozen=True requires object.__setattr__ for defaults
        if self.project_root is None:
            object.__setattr__(self, "project_root", Path.cwd())

    @classmethod
    def detect(cls) -> Context:
        """Build context from environment variables."""
        run_id = os.getenv("GITHUB_RUN_ID", "")
        repository = os.getenv("GITHUB_REPOSITORY", "")
        commit_sha = os.getenv("GITHUB_SHA", "")

        run_url = ""
        if repository and run_id:
            run_url = f"https://github.com/{repository}/actions/runs/{run_id}"

        return cls(
            commit_sha=commit_sha,
            workflow_name=os.getenv("GITHUB_WORKFLOW", ""),
            job_name=os.getenv("GITHUB_JOB", ""),
            run_id=run_id,
            run_number=os.getenv("GITHUB_RUN_NUMBER", ""),
            repository=repository,
            actor=os.getenv("GITHUB_ACTOR", ""),
            branch=os.getenv("GITHUB_REF_NAME", ""),
            event_name=os.getenv("GITHUB_EVENT_NAME", ""),
            ref=os.getenv("GITHUB_REF", ""),
            run_url=run_url,
            is_github_actions=bool(run_id),
            is_interactive=sys.stdin.isatty(),
            step_summary_path=os.getenv("GITHUB_STEP_SUMMARY", ""),
            project_root=Path.cwd(),
        )
