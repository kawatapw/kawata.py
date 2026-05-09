#!/usr/bin/env python3
"""
Parse bandit JSON output and generate a concise summary for GitHub Actions.

This script reads bandit's JSON output and extracts only the relevant information
to avoid exceeding GitHub's 1MB step summary limit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def parse_bandit_output(json_file: Path) -> dict[str, Any]:
    """Parse bandit JSON output and extract relevant information."""
    if not json_file.exists():
        return {"error": f"File not found: {json_file}"}

    try:
        with open(json_file) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}

    # Filter out third-party issues (files in .denv, .venv, venv, site-packages, etc.)
    def is_project_file(filename: str) -> bool:
        """Check if the file belongs to the project (not third-party)."""
        # Exclude virtual environment directories
        excluded_patterns = [
            ".denv/",
            ".venv/",
            "venv/",
            "site-packages/",
            "__pycache__/",
            "tests/",
            "testing/",
            "migrations/",
            "tools/",
        ]
        filename_lower = filename.lower()
        return not any(pattern in filename_lower for pattern in excluded_patterns)

    # Filter results to only include project files
    project_results = [
        issue
        for issue in data.get("results", [])
        if is_project_file(issue.get("filename", ""))
    ]

    # Extract summary information
    summary: dict[str, Any] = {
        "total_issues": len(project_results),
        "high_severity": 0,
        "medium_severity": 0,
        "low_severity": 0,
        "issues": [],
    }

    # Count severity levels
    for issue in project_results:
        severity = issue.get("issue_severity", "").upper()
        if severity == "HIGH":
            summary["high_severity"] += 1
        elif severity == "MEDIUM":
            summary["medium_severity"] += 1
        elif severity == "LOW":
            summary["low_severity"] += 1

        # Add issue details (limit to first 10 issues to avoid overflow)
        if len(summary["issues"]) < 10:
            # Extract code snippet if available
            code_snippet = issue.get("code", "")
            if code_snippet:
                # Take first line of code snippet and truncate to 50 chars
                code_lines = code_snippet.split("\n")
                code_snippet = (
                    code_lines[0][:50] + "..."
                    if len(code_lines[0]) > 50
                    else code_lines[0]
                )

            summary["issues"].append(
                {
                    "test_id": issue.get("test_id", ""),
                    "severity": severity,
                    "confidence": issue.get("issue_confidence", "").upper(),
                    "file": issue.get("filename", ""),
                    "line": issue.get("line_number", 0),
                    "issue_text": issue.get("issue_text", "")[
                        :80
                    ],  # Truncate long text
                    "code": code_snippet,
                },
            )

    return summary


def format_summary(summary: dict[str, Any]) -> str:
    """Format the summary for GitHub Actions step summary."""
    if "error" in summary:
        return f"## Bandit Results\n\n❌ Error: {summary['error']}\n"

    lines = ["## Bandit Security Scan Results\n"]

    # Summary statistics
    lines.append("### Summary\n")
    lines.append(f"- **Total Issues Found**: {summary['total_issues']}\n")
    lines.append(f"- **High Severity**: {summary['high_severity']}\n")
    lines.append(f"- **Medium Severity**: {summary['medium_severity']}\n")
    lines.append(f"- **Low Severity**: {summary['low_severity']}\n")
    lines.append("\n")

    # Issue details
    if summary["issues"]:
        lines.append("### Issues (First 10)\n")
        for i, issue in enumerate(summary["issues"], 1):
            lines.append(f"#### {i}. {issue['severity']} - {issue['test_id']}\n")
            lines.append(f"- **File**: `{issue['file']}` (line {issue['line']})\n")
            lines.append(f"- **Confidence**: {issue['confidence']}\n")
            lines.append(f"- **Issue**: {issue['issue_text']}\n")
            if issue.get("code"):
                lines.append(f"- **Code**: `{issue['code']}`\n")
            lines.append("\n")

        # Add note about total issues
        if summary["total_issues"] > 10:
            lines.append(
                f"**Note**: Showing first 10 of {summary['total_issues']} total issues.\n",
            )
    else:
        lines.append("### Issues\n")
        lines.append("✅ No issues found!\n")

    return "".join(lines)


def main() -> None:
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: parse_bandit.py <bandit_json_file>")
        sys.exit(1)

    json_file = Path(sys.argv[1])
    summary = parse_bandit_output(json_file)
    formatted = format_summary(summary)
    print(formatted)

    # Exit with error code if high/medium severity issues found
    if summary.get("high_severity", 0) > 0 or summary.get("medium_severity", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
