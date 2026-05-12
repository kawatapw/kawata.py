"""Parser for bandit security scanner JSON output."""

from __future__ import annotations

import json

from ci_tool.parsers import Parser, registry
from ci_tool.parsers.models import CodeSnippet, Issue, ParsedResult, Severity


class BanditParser(Parser):
    """Parser for bandit JSON output."""

    SEVERITY_MAP = {
        "HIGH": Severity.HIGH,
        "MEDIUM": Severity.MEDIUM,
        "LOW": Severity.LOW,
    }

    @property
    def name(self) -> str:
        return "bandit"

    @property
    def supported_filenames(self) -> list[str]:
        return ["bandit"]

    def parse(self, content: str, file_path: str = "") -> ParsedResult:
        result = ParsedResult(parser_name=self.name, file_path=file_path)

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            result.parse_error = f"JSON parse error: {e}"
            return result

        # Metrics are keyed by filename; aggregate totals live under "_totals".
        # e.g. metrics["_totals"]["SEVERITY.HIGH"] = 3
        metrics = data.get("metrics", {})
        totals = metrics.get("_totals", {})

        result.high = totals.get("SEVERITY.HIGH", 0)
        result.medium = totals.get("SEVERITY.MEDIUM", 0)
        result.low = totals.get("SEVERITY.LOW", 0)

        results_list = data.get("results", [])
        result.total = len(results_list)
        # Set errors so summary_line() and has_failures work for security scanners
        result.errors = result.total

        issues: list[Issue] = []
        for item in results_list:
            severity_str = item.get("issue_severity", "LOW")
            sev = self.SEVERITY_MAP.get(severity_str, Severity.LOW)

            filename = item.get("filename", "")
            line_number = item.get("line_number", 0)

            snippet = CodeSnippet(
                file_path=filename,
                line_number=line_number,
                source=self._read_source_lines(filename, line_number),
                column=item.get("col_offset", 0),
            )

            issues.append(
                Issue(
                    file_path=filename,
                    line_number=line_number,
                    column=item.get("col_offset", 0),
                    severity=sev,
                    message=item.get("issue_text", ""),
                    rule_id=item.get("test_id", ""),
                    rule_name=item.get("test_name", ""),
                    code_snippet=snippet,
                    cve_id=item.get("issue_cwe", {}).get("id", ""),
                )
            )

        result.issues = issues
        return result


registry.register(BanditParser())
