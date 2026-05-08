"""Ruff linter parser."""

from __future__ import annotations

import json
import re
from typing import Any

from .registry import Parser
from .registry import register_parser


class RuffParser(Parser):
    """Parser for Ruff linter output (text and JSON formats)."""

    # Regex pattern for ruff text output
    # Format: path/to/file.py:line:col: RULE_CODE Message
    RUFF_TEXT_PATTERN = re.compile(
        r"^(?P<file>[^:]+):(?P<line>\d+):(?P<column>\d+):\s*"
        r"(?P<rule_code>[A-Z]+\d+)\s+(?P<message>.+)$",
    )

    def parse(self, content: str) -> dict[str, Any]:
        """Parse Ruff output content (auto-detects text or JSON)."""
        content = content.strip()

        # Try to parse as JSON first
        if content.startswith("[") or content.startswith("{"):
            try:
                data = json.loads(content)
                return self._parse_json(data)
            except json.JSONDecodeError:
                pass

        # Parse as text format
        return self._parse_text(content)

    def _parse_json(self, data: Any) -> dict[str, Any]:
        """Parse Ruff JSON output."""
        violations: list[dict[str, Any]] = []
        rules_count: dict[str, int] = {}

        # Handle both list and dict formats
        items = data if isinstance(data, list) else data.get("violations", [])

        for item in items:
            rule_code = item.get("code", item.get("rule_code", ""))
            location = item.get("location", {})
            end_location = item.get("end_location", {})

            violation = {
                "file": item.get("filename", ""),
                "line": location.get("row", 0),
                "column": location.get("column", 0),
                "end_line": end_location.get("row", 0),
                "end_column": end_location.get("column", 0),
                "rule_code": rule_code,
                "message": item.get("message", ""),
                "fixable": item.get("fix") is not None,
            }

            violations.append(violation)

            # Count rules
            if rule_code:
                rules_count[rule_code] = rules_count.get(rule_code, 0) + 1

        fixable_count = sum(1 for v in violations if v["fixable"])

        return {
            "type": "ruff",
            "summary": {
                "total_violations": len(violations),
                "fixable": fixable_count,
                "rules": rules_count,
            },
            "violations": violations,
        }

    def _parse_text(self, content: str) -> dict[str, Any]:
        """Parse Ruff text output."""
        violations: list[dict[str, Any]] = []
        rules_count: dict[str, int] = {}

        for line in content.split("\n"):
            if not line.strip():
                continue

            match = self.RUFF_TEXT_PATTERN.match(line)
            if match:
                rule_code = match.group("rule_code")

                violation = {
                    "file": match.group("file"),
                    "line": int(match.group("line")),
                    "column": int(match.group("column")),
                    "rule_code": rule_code,
                    "message": match.group("message").strip(),
                    "fixable": False,  # Text format doesn't indicate fixability
                }

                violations.append(violation)

                # Count rules
                if rule_code:
                    rules_count[rule_code] = rules_count.get(rule_code, 0) + 1

        return {
            "type": "ruff",
            "summary": {
                "total_violations": len(violations),
                "fixable": 0,
                "rules": rules_count,
            },
            "violations": violations,
        }

    def get_type(self) -> str:
        """Get parser type name."""
        return "ruff"


# Register the parser
register_parser("ruff", RuffParser)
