"""Lightweight helpers for interacting with the GitHub REST API.

These utilities are intentionally small wrappers around common operations
needed by the CI tool (creating and updating check runs, building headers,
and discovering repository context) so that higher-level modules do not
need to know about environment variable names or HTTP details.
"""

import os
from typing import Any, cast

import requests


def get_github_token() -> str | None:
    """Return the GitHub token from the current environment, if any.

    The function checks the typical variables that are available in
    GitHub Actions contexts.

    Returns:
        The token string, or ``None`` if no token could be found.
    """
    return os.getenv("GITHUB_TOKEN") or os.getenv("INPUT_GITHUB_TOKEN")


def get_github_headers() -> dict[str, str]:
    """Build a headers dictionary suitable for GitHub API requests.

    Includes the appropriate ``Accept`` and ``User-Agent`` headers and, if
    a token is available, an ``Authorization`` header.

    Returns:
        A dictionary of HTTP headers.
    """
    token = get_github_token()
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "ci-tool"}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def get_repository() -> str | None:
    """Return the ``owner/repo`` identifier from the environment, if set."""
    return os.getenv("GITHUB_REPOSITORY")


def get_api_url() -> str:
    """Return the base URL for the GitHub API.

    This respects the `GITHUB_API_URL` environment variable to support
    GitHub Enterprise instances, defaulting to the public API URL.
    """
    return os.getenv("GITHUB_API_URL", "https://api.github.com")


def create_check_run(
    name: str,
    head_sha: str,
    status: str = "in_progress",
    output: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Create a GitHub check run for the given commit.

    Args:
        name: Human-readable name for the check run.
        head_sha: Commit SHA the check run should be associated with.
        status: Initial status for the run (for example ``\"in_progress\"``).
        output: Optional payload describing the run output as expected by
            the GitHub Checks API.

    Returns:
        The deserialized JSON response from the API on success, or
        ``None`` if the repository could not be determined or an error
        occurs during the request.
    """
    repo = get_repository()
    if not repo:
        return None

    url = f"{get_api_url()}/repos/{repo}/check-runs"
    headers = get_github_headers()

    data: dict[str, Any] = {"name": name, "head_sha": head_sha, "status": status}

    if output:
        data["output"] = output

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return cast(dict[str, Any] | None, response.json())
    except Exception as e:
        print(f"Failed to create check run: {e}")
        return None


def update_check_run(
    check_run_id: int,
    name: str,
    status: str,
    conclusion: str | None = None,
    output: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Update an existing GitHub check run.

    Args:
        check_run_id: Identifier of the check run to update.
        name: Display name for the check run.
        status: New status value (for example ``\"completed\"``).
        conclusion: Optional final conclusion (such as ``\"success\"`` or
            ``\"failure\"``) when marking a run completed.
        output: Optional updated output payload for the run.

    Returns:
        The deserialized JSON response from the API on success, or
        ``None`` if the repository could not be determined or an error
        occurs during the request.
    """
    repo = get_repository()
    if not repo:
        return None

    url = f"{get_api_url()}/repos/{repo}/check-runs/{check_run_id}"
    headers = get_github_headers()

    data: dict[str, Any] = {"name": name, "status": status}

    if conclusion:
        data["conclusion"] = conclusion

    if output:
        data["output"] = output

    try:
        response = requests.patch(url, headers=headers, json=data)
        response.raise_for_status()
        return cast(dict[str, Any] | None, response.json())
    except Exception as e:
        print(f"Failed to update check run: {e}")
        return None
