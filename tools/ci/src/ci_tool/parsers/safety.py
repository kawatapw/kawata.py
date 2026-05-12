"""Parser for safety dependency vulnerability scanner."""

from __future__ import annotations

import json
import re

from ci_tool.parsers import Parser, registry
from ci_tool.parsers.models import Issue, ParsedResult, Severity


class SafetyParser(Parser):
    """Parser for safety JSON output."""

    @property
    def name(self) -> str:
        return "safety"

    @property
    def supported_filenames(self) -> list[str]:
        return ["safety"]

    def parse(self, content: str, file_path: str = "") -> ParsedResult:
        result = ParsedResult(parser_name=self.name, file_path=file_path)

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            result.parse_error = f"JSON parse error: {e}"
            return result

        issues: list[Issue] = []
        vulns_data = data.get("vulnerabilities", [])

        if isinstance(vulns_data, dict):
            for pkg_name, pkg_vulns in vulns_data.items():
                for vuln in pkg_vulns:
                    issues.append(self._parse_vulnerability(vuln, pkg_name))
        elif isinstance(vulns_data, list):
            for vuln in vulns_data:
                pkg = vuln.get("package", vuln.get("package_name", ""))
                issues.append(self._parse_vulnerability(vuln, pkg))

        for issue in issues:
            if issue.severity == Severity.CRITICAL:
                result.critical += 1
            elif issue.severity == Severity.HIGH:
                result.high += 1
            elif issue.severity == Severity.MEDIUM:
                result.medium += 1
            else:
                result.low += 1

        scanned = data.get("scanned_packages", {})
        result.packages_scanned = len(scanned) if isinstance(scanned, dict) else 0
        result.total = len(issues)
        result.issues = issues
        return result

    def _parse_vulnerability(self, vuln: dict, package_name: str = "") -> Issue:
        severity_str = vuln.get("severity", "low").lower()
        if severity_str not in ("critical", "high", "medium", "low"):
            advisory = vuln.get("advisory", "").lower()
            if "critical" in advisory:
                severity_str = "critical"
            elif "high" in advisory:
                severity_str = "high"
            elif "medium" in advisory:
                severity_str = "medium"
            else:
                severity_str = "low"

        severity = Severity(severity_str)

        cve = vuln.get("cve", vuln.get("CVE", ""))
        if not cve:
            advisory = vuln.get("advisory", "")
            match = re.search(r"CVE-\d{4}-\d+", advisory)
            if match:
                cve = match.group(0)

        return Issue(
            file_path="",
            line_number=0,
            severity=severity,
            message=vuln.get("advisory", vuln.get("description", "")),
            rule_id=str(vuln.get("id", vuln.get("vulnerability_id", ""))),
            package=vuln.get("package", package_name),
            installed_version=vuln.get(
                "installed_version", vuln.get("analyzed_version", "")
            ),
            cve_id=cve or "",
        )


registry.register(SafetyParser())
