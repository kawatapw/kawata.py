"""Parser for ruff linter output (text and JSON)."""

from __future__ import annotations

import json
import re

from ci_tool.parsers import Parser, registry
from ci_tool.parsers.models import CodeSnippet, Issue, ParsedResult, Severity


class RuffParser(Parser):
    """Parser for ruff text and JSON output."""

    TEXT_PATTERN = re.compile(
        r"^(?P<file>[^:]+):(?P<line>\d+):(?P<column>\d+):\s*"
        r"(?P<rule_code>[A-Z]+\d+)\s+(?P<message>.+)$",
    )

    @property
    def name(self) -> str:
        return "ruff"

    @property
    def supported_filenames(self) -> list[str]:
        return ["ruff"]

    def parse(self, content: str, file_path: str = "") -> ParsedResult:
        content = content.strip()

        # Try JSON first
        if content.startswith("[") or content.startswith("{"):
            try:
                data = json.loads(content)
                return self._parse_json(data, file_path)
            except json.JSONDecodeError:
                pass

        return self._parse_text(content, file_path)

    def _parse_json(self, data: list | dict, file_path: str) -> ParsedResult:
        result = ParsedResult(parser_name=self.name, file_path=file_path)
        issues: list[Issue] = []

        items = data if isinstance(data, list) else data.get("violations", [])

        for item in items:
            rule_code = item.get("code", item.get("rule_code", ""))
            location = item.get("location", {})
            end_location = item.get("end_location", {})
            row = location.get("row", 0)
            col = location.get("column", 0)

            snippet = None
            fname = item.get("filename", "")
            if fname and row > 0:
                source = self._read_source_lines(fname, row)
                if source:
                    snippet = CodeSnippet(
                        file_path=fname,
                        line_number=row,
                        source=source,
                        column=col,
                        end_column=end_location.get("column", 0),
                    )

            issues.append(
                Issue(
                    file_path=fname,
                    line_number=row,
                    column=col,
                    end_line_number=end_location.get("row", 0),
                    end_column=end_location.get("column", 0),
                    severity=Severity.ERROR,
                    message=item.get("message", ""),
                    rule_id=rule_code,
                    code_snippet=snippet,
                )
            )

        result.errors = len(issues)
        result.issues = issues
        return result

    def _parse_text(self, content: str, file_path: str) -> ParsedResult:
        result = ParsedResult(parser_name=self.name, file_path=file_path)
        issues: list[Issue] = []

        for line in content.split("\n"):
            if not line.strip():
                continue

            match = self.TEXT_PATTERN.match(line)
            if not match:
                continue

            fname = match.group("file")
            line_num = int(match.group("line"))
            rule_code = match.group("rule_code")

            snippet = None
            source = self._read_source_lines(fname, line_num)
            if source:
                snippet = CodeSnippet(
                    file_path=fname,
                    line_number=line_num,
                    source=source,
                    column=int(match.group("column")),
                )

            issues.append(
                Issue(
                    file_path=fname,
                    line_number=line_num,
                    column=int(match.group("column")),
                    severity=Severity.ERROR,
                    message=match.group("message").strip(),
                    rule_id=rule_code,
                    code_snippet=snippet,
                )
            )

        result.errors = len(issues)
        result.issues = issues
        return result


registry.register(RuffParser())
