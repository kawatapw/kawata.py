"""Unit tests for context module."""

import os
import sys
from pathlib import Path

# Add tools/ci to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tools" / "ci"))

from core.context import build_context


def test_build_context_github_actions():
    """Test building context in GitHub Actions environment."""
    # Set up GitHub environment variables
    os.environ["GITHUB_SHA"] = "abc123"
    os.environ["GITHUB_WORKFLOW"] = "test-workflow"
    os.environ["GITHUB_JOB"] = "test-job"
    os.environ["GITHUB_RUN_ID"] = "123456"
    os.environ["GITHUB_RUN_NUMBER"] = "1"
    os.environ["GITHUB_REPOSITORY"] = "owner/repo"
    os.environ["GITHUB_ACTOR"] = "test-user"
    os.environ["GITHUB_STEP_SUMMARY"] = "/tmp/step-summary.md"  # nosec B108

    context = build_context()

    assert context.commit_sha == "abc123"
    assert context.workflow_name == "test-workflow"
    assert context.job_name == "test-job"
    assert context.run_id == "123456"
    assert context.run_number == "1"
    assert context.repository == "owner/repo"
    assert context.actor == "test-user"
    assert context.is_github_actions is True
    assert context.step_summary_path == "/tmp/step-summary.md"  # nosec B108
    assert context.run_url == "https://github.com/owner/repo/actions/runs/123456"

    # Clean up environment variables
    for key in [
        "GITHUB_SHA",
        "GITHUB_WORKFLOW",
        "GITHUB_JOB",
        "GITHUB_RUN_ID",
        "GITHUB_RUN_NUMBER",
        "GITHUB_REPOSITORY",
        "GITHUB_ACTOR",
        "GITHUB_STEP_SUMMARY",
    ]:
        os.environ.pop(key, None)


def test_build_context_local():
    """Test building context in local environment."""
    # Clear GitHub environment variables
    for key in [
        "GITHUB_SHA",
        "GITHUB_WORKFLOW",
        "GITHUB_JOB",
        "GITHUB_RUN_ID",
        "GITHUB_RUN_NUMBER",
        "GITHUB_REPOSITORY",
        "GITHUB_ACTOR",
        "GITHUB_STEP_SUMMARY",
    ]:
        os.environ.pop(key, None)

    context = build_context()

    assert context.commit_sha == ""
    assert context.workflow_name == ""
    assert context.job_name == ""
    assert context.run_id == ""
    assert context.run_number == ""
    assert context.repository == ""
    assert context.actor == ""
    assert context.is_github_actions is False
    assert context.step_summary_path is None
    assert context.run_url == ""
