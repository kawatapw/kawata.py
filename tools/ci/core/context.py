"""Runtime and GitHub Actions execution context for the CI tool.

This module centralizes information about the environment the CI tool is
running in, with a strong focus on GitHub Actions metadata. The `Context`
object is deliberately kept lightweight and immutable so it can be safely
passed around to modules that need to understand:

- Which commit and workflow are currently executing
- How to construct links back to the GitHub run UI
- Whether the tool is running inside GitHub Actions or locally
- Whether the current process is attached to an interactive terminal
"""

import os
import sys
from dataclasses import dataclass


@dataclass
class Context:
    """Execution context derived from the current environment.

    When running under GitHub Actions this is mostly a thin wrapper around
    `GITHUB_*` environment variables. When running locally the fields are
    present but typically empty, and `is_github_actions` is `False`.

    Attributes:
        commit_sha: SHA of the commit being built or tested.
        workflow_name: Logical GitHub Actions workflow name.
        job_name: Name of the current GitHub Actions job.
        run_id: Numeric identifier for the GitHub Actions run.
        run_number: Incrementing run number for the workflow.
        repository: `owner/repo` string for the repository.
        actor: User or bot that triggered the run.
        run_url: Fully-qualified URL to the GitHub Actions run, if available.
        is_github_actions: True if running inside GitHub Actions.
        is_interactive: True if stdin is attached to a TTY.
        step_summary_path: Path to `GITHUB_STEP_SUMMARY`, if set.
    """

    commit_sha: str
    workflow_name: str
    job_name: str
    run_id: str
    run_number: str
    repository: str
    actor: str
    run_url: str
    is_github_actions: bool
    is_interactive: bool
    step_summary_path: str | None


def build_context() -> Context:
    """Construct a `Context` instance from process environment variables.

    This helper performs all environment probing required by the CI tool
    and produces a single `Context` object that can be threaded through
    the rest of the codebase. It degrades gracefully outside of GitHub
    Actions by leaving GitHub-specific fields empty and marking
    `is_github_actions` as `False`.

    Returns:
        A populated `Context` instance representing the current environment.
    """
    github_sha = os.getenv("GITHUB_SHA", "")
    github_workflow = os.getenv("GITHUB_WORKFLOW", "")
    github_job = os.getenv("GITHUB_JOB", "")
    github_run_id = os.getenv("GITHUB_RUN_ID", "")
    github_run_number = os.getenv("GITHUB_RUN_NUMBER", "")
    github_repository = os.getenv("GITHUB_REPOSITORY", "")
    github_actor = os.getenv("GITHUB_ACTOR", "")
    github_step_summary = os.getenv("GITHUB_STEP_SUMMARY")

    # Detect if running in GitHub Actions
    is_github_actions = bool(github_run_id)

    # Detect if running in interactive terminal
    is_interactive = sys.stdin.isatty()

    # Build run URL
    run_url = ""
    if github_repository and github_run_id:
        run_url = f"https://github.com/{github_repository}/actions/runs/{github_run_id}"

    return Context(
        commit_sha=github_sha,
        workflow_name=github_workflow,
        job_name=github_job,
        run_id=github_run_id,
        run_number=github_run_number,
        repository=github_repository,
        actor=github_actor,
        run_url=run_url,
        is_github_actions=is_github_actions,
        is_interactive=is_interactive,
        step_summary_path=github_step_summary,
    )
