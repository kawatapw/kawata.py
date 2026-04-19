"""Mypy type checker parser."""

import re
from typing import Any

from .registry import Parser, register_parser


class MypyParser(Parser):
    """Parser for Mypy type checker output."""

    # Regex pattern for mypy output lines
    # Format: path/to/file.py:line: severity: Message [error-code]
    MYPY_PATTERN = re.compile(
        r"^(?P<file>[^:]+):(?P<line>\d+):(?:(?P<end_line>\d+):)?\s*"
        r"(?P<severity>error|note|warning):\s*(?P<message>.+?)"
        r"(?:\s*\[(?P<error_code>[^\]]+)\])?$",
    )

    def parse(self, content: str) -> dict[str, Any]:
        """Parse Mypy output content."""
        issues: list[dict[str, Any]] = []
        files_with_errors = set()

        for line in content.strip().split("\n"):
            if not line.strip():
                continue

            match = self.MYPY_PATTERN.match(line)
            if match:
                file_path = match.group("file")
                severity = match.group("severity")

                issue = {
                    "file": file_path,
                    "line": int(match.group("line")),
                    "severity": severity,
                    "message": match.group("message").strip(),
                    "error_code": match.group("error_code"),
                }

                # Add end_line if present
                end_line = match.group("end_line")
                if end_line:
                    issue["end_line"] = int(end_line)

                issues.append(issue)

                if severity == "error":
                    files_with_errors.add(file_path)

        # Calculate summary
        total_errors = sum(1 for i in issues if i["severity"] == "error")
        total_notes = sum(1 for i in issues if i["severity"] == "note")
        total_warnings = sum(1 for i in issues if i["severity"] == "warning")

        return {
            "type": "mypy",
            "summary": {
                "total_issues": len(issues),
                "total_errors": total_errors,
                "total_notes": total_notes,
                "total_warnings": total_warnings,
                "files_with_errors": len(files_with_errors),
            },
            "issues": issues,
        }

    def get_type(self) -> str:
        """Get parser type name."""
        return "mypy"


# Register the parser
register_parser("mypy", MypyParser)
