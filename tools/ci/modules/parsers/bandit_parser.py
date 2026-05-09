"""Bandit security scanner parser."""

from __future__ import annotations

import json
from typing import Any

from .registry import Parser
from .registry import register_parser


class BanditParser(Parser):
    """Parser for Bandit security scan results."""

    def parse(self, content: str) -> dict[str, Any]:
        """Parse Bandit JSON content."""
        data = json.loads(content)

        # Extract summary
        summary = {
            "total_issues": data.get("metrics", {}).get("total", 0),
            "high_severity": data.get("metrics", {}).get("SEVERITY.HIGH", 0),
            "medium_severity": data.get("metrics", {}).get("SEVERITY.MEDIUM", 0),
            "low_severity": data.get("metrics", {}).get("SEVERITY.LOW", 0),
            "confidence_high": data.get("metrics", {}).get("CONFIDENCE.HIGH", 0),
            "confidence_medium": data.get("metrics", {}).get("CONFIDENCE.MEDIUM", 0),
            "confidence_low": data.get("metrics", {}).get("CONFIDENCE.LOW", 0),
        }

        # Extract issues
        issues = []
        for issue in data.get("results", []):
            issues.append(
                {
                    "severity": issue.get("issue_severity", "UNKNOWN"),
                    "confidence": issue.get("issue_confidence", "UNKNOWN"),
                    "test_id": issue.get("test_id", ""),
                    "test_name": issue.get("test_name", ""),
                    "issue_text": issue.get("issue_text", ""),
                    "line_number": issue.get("line_number", 0),
                    "line_range": issue.get("line_range", []),
                    "file_path": issue.get("filename", ""),
                    "more_info": issue.get("more_info", ""),
                },
            )

        return {"type": "bandit", "summary": summary, "issues": issues}

    def get_type(self) -> str:
        """Get parser type name."""
        return "bandit"


# Register the parser
register_parser("bandit", BanditParser)
