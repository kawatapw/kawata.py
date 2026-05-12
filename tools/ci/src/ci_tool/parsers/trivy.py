"""Parser for trivy vulnerability scanner (SARIF and JSON)."""

from __future__ import annotations

import json

from ci_tool.parsers import Parser, registry
from ci_tool.parsers.models import Issue, ParsedResult, Severity

SARIF_LEVEL_MAP = {
    "error": Severity.CRITICAL,
    "warning": Severity.HIGH,
    "note": Severity.MEDIUM,
    "info": Severity.LOW,
}


class TrivyParser(Parser):
    """Parser for trivy SARIF and JSON output."""

    @property
    def name(self) -> str:
        return "trivy"

    @property
    def supported_filenames(self) -> list[str]:
        return ["trivy"]

    @property
    def supported_extensions(self) -> list[str]:
        return [".sarif"]

    def parse(self, content: str, file_path: str = "") -> ParsedResult:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            result = ParsedResult(parser_name=self.name, file_path=file_path)
            result.parse_error = f"JSON parse error: {e}"
            return result

        # Detect format
        if isinstance(data, dict) and "$schema" in data:
            schema = data.get("$schema", "")
            if "sarif" in schema.lower():
                return self._parse_sarif(data, file_path)

        return self._parse_json(data, file_path)

    def _parse_sarif(self, data: dict, file_path: str) -> ParsedResult:
        result = ParsedResult(parser_name=self.name, file_path=file_path)
        issues: list[Issue] = []

        for run in data.get("runs", []):
            for r in run.get("results", []):
                level = r.get("level", "warning")
                severity = SARIF_LEVEL_MAP.get(level, Severity.LOW)

                if severity == Severity.CRITICAL:
                    result.critical += 1
                elif severity == Severity.HIGH:
                    result.high += 1
                elif severity == Severity.MEDIUM:
                    result.medium += 1
                else:
                    result.low += 1

                rule_id = r.get("ruleId", "")
                cve_id = rule_id if rule_id.startswith("CVE-") else ""

                issues.append(
                    Issue(
                        file_path="",
                        line_number=0,
                        severity=severity,
                        message=r.get("message", {}).get("text", ""),
                        rule_id=rule_id,
                        cve_id=cve_id,
                    )
                )

        result.total = len(issues)
        result.issues = issues
        return result

    def _parse_json(self, data: dict, file_path: str) -> ParsedResult:
        result = ParsedResult(parser_name=self.name, file_path=file_path)
        issues: list[Issue] = []

        results_list = data.get("Results", data.get("results", []))
        for r in results_list:
            for vuln in r.get("Vulnerabilities", r.get("vulnerabilities", [])):
                severity_str = vuln.get("Severity", "UNKNOWN").lower()
                try:
                    severity = Severity(severity_str)
                except ValueError:
                    severity = Severity.LOW

                if severity == Severity.CRITICAL:
                    result.critical += 1
                elif severity == Severity.HIGH:
                    result.high += 1
                elif severity == Severity.MEDIUM:
                    result.medium += 1
                else:
                    result.low += 1

                issues.append(
                    Issue(
                        file_path="",
                        line_number=0,
                        severity=severity,
                        message=vuln.get("Title", vuln.get("title", "")),
                        rule_id=vuln.get("VulnerabilityID", vuln.get("id", "")),
                        package=vuln.get("PkgName", vuln.get("package", "")),
                        installed_version=vuln.get("InstalledVersion", ""),
                        fixed_version=vuln.get("FixedVersion", ""),
                    )
                )

        result.total = len(issues)
        result.issues = issues
        return result


registry.register(TrivyParser())
