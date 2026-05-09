"""Command-line interface definition for the CI tool.

This module centralizes all argument parsing so other parts of the system
can rely on a single, well-defined `argparse` schema. The CLI follows a
``ci <module> <action> [FLAGS]`` pattern where modules correspond to major
capabilities such as workflow tracking, summary generation, and reports.
"""

from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    """Parse and return command-line arguments for the CI tool.

    The parsed object includes:

    - Global flags such as ``--storage``, ``--config``, ``--verbose``,
      ``--debug`` and ``--json``
    - A ``module`` attribute selecting the top-level command group
    - An ``action`` attribute selecting the sub-command within that module
    - Additional flags specific to each module/action combination

    Returns:
        An `argparse.Namespace` instance suitable for passing to other
        core helpers such as configuration loading and dispatch logic.
    """
    parser = argparse.ArgumentParser(prog="ci", description="CI orchestration tool")

    # Global flags
    parser.add_argument("--storage", help="Storage backend")
    parser.add_argument("--config", help="Config file path")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--json", action="store_true")

    # Subparsers for modules
    subparsers = parser.add_subparsers(dest="module", help="Module name")

    # Workflow module
    workflow_parser = subparsers.add_parser("workflow", help="Workflow lifecycle")
    workflow_subparsers = workflow_parser.add_subparsers(dest="action")

    # Workflow start: can be workflow-level or job-scoped
    start_parser = workflow_subparsers.add_parser("start", help="Start workflow or job")
    start_parser.add_argument(
        "--workflow",
        help="Workflow name to start (defaults to GITHUB_WORKFLOW)",
    )
    start_parser.add_argument(
        "--job",
        help="Optional job name to start (defaults to GITHUB_JOB when omitted)",
    )

    # Workflow finish: can be workflow-level or job-scoped
    finish_parser = workflow_subparsers.add_parser(
        "finish",
        help="Finish workflow or job",
    )
    finish_parser.add_argument(
        "--workflow",
        help="Workflow name to finish (defaults to GITHUB_WORKFLOW)",
    )
    finish_parser.add_argument(
        "--job",
        help="Optional job name to finish (defaults to GITHUB_JOB when omitted)",
    )
    finish_parser.add_argument(
        "--status",
        help="Status to record (e.g. success/failure)",
    )

    # Summary module
    summary_parser = subparsers.add_parser("summary", help="Job summaries")
    summary_subparsers = summary_parser.add_subparsers(dest="action")
    generate_parser = summary_subparsers.add_parser("generate", help="Generate summary")
    generate_parser.add_argument("--workflow", help="Workflow name to summarize")
    generate_parser.add_argument("--run-id", help="Run ID to summarize")
    generate_parser.add_argument(
        "--artifact-dir",
        help="Directory containing artifacts",
    )

    # Report module
    report_parser = subparsers.add_parser("report", help="CI reports")
    report_subparsers = report_parser.add_subparsers(dest="action")
    report_subparsers.add_parser("aggregate", help="Aggregate reports")

    # Artifacts module
    artifacts_parser = subparsers.add_parser("artifacts", help="Artifact management")
    artifacts_subparsers = artifacts_parser.add_subparsers(dest="action")
    artifacts_subparsers.add_parser("collect", help="Collect artifacts")

    return parser.parse_args()
