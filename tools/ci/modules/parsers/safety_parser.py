"""Safety dependency vulnerability scanner parser."""

from __future__ import annotations

import json
from typing import Any

from .registry import Parser
from .registry import register_parser


class SafetyParser(Parser):
    """Parser for Safety dependency vulnerability scanner output."""

    def parse(self, content: str) -> dict[str, Any]:
        """Parse Safety JSON output."""
        data = json.loads(content)

        vulnerabilities: list[dict[str, Any]] = []
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

        # Handle different Safety output formats
        vulns_data = data.get("vulnerabilities", [])

        # Safety can return vulnerabilities as a list or dict
        if isinstance(vulns_data, dict):
            # Format: {"package-name": [{vuln1}, {vuln2}, ...]}
            for package_name, package_vulns in vulns_data.items():
                for vuln in package_vulns:
                    parsed = self._parse_vulnerability(vuln, package_name)
                    vulnerabilities.append(parsed)
                    self._count_severity(parsed["severity"], severity_counts)
        elif isinstance(vulns_data, list):
            # Format: [{vuln1}, {vuln2}, ...]
            for vuln in vulns_data:
                package_name = vuln.get("package", vuln.get("package_name", ""))
                parsed = self._parse_vulnerability(vuln, package_name)
                vulnerabilities.append(parsed)
                self._count_severity(parsed["severity"], severity_counts)

        # Get scanned packages count
        scanned_packages = data.get("scanned_packages", {})
        packages_scanned = (
            len(scanned_packages) if isinstance(scanned_packages, dict) else 0
        )

        return {
            "type": "safety",
            "summary": {
                "total_vulnerabilities": len(vulnerabilities),
                "packages_scanned": packages_scanned,
                **severity_counts,
            },
            "vulnerabilities": vulnerabilities,
        }

    def _parse_vulnerability(
        self,
        vuln: dict[str, Any],
        package_name: str = "",
    ) -> dict[str, Any]:
        """Parse a single vulnerability entry."""
        # Extract vulnerability ID
        vuln_id = str(vuln.get("id", vuln.get("vulnerability_id", "")))

        # Extract severity
        severity = vuln.get("severity", "unknown").lower()
        if severity not in ("critical", "high", "medium", "low"):
            # Try to infer from advisory
            advisory = vuln.get("advisory", "").lower()
            if "critical" in advisory:
                severity = "critical"
            elif "high" in advisory:
                severity = "high"
            elif "medium" in advisory:
                severity = "medium"
            else:
                severity = "low"

        # Extract package info
        pkg = vuln.get("package", package_name)
        installed_version = vuln.get(
            "installed_version",
            vuln.get("analyzed_version", ""),
        )
        affected_versions = vuln.get("affected_versions", vuln.get("affected_spec", ""))

        # Extract CVE
        cve = vuln.get("cve", vuln.get("CVE", ""))
        if not cve:
            # Try to extract from advisory
            advisory = vuln.get("advisory", "")
            if "CVE-" in advisory:
                import re

                cve_match = re.search(r"CVE-\d{4}-\d+", advisory)
                if cve_match:
                    cve = cve_match.group(0)

        return {
            "id": vuln_id,
            "package": pkg,
            "installed_version": installed_version,
            "affected_versions": affected_versions,
            "severity": severity,
            "cve": cve or None,
            "description": vuln.get("advisory", vuln.get("description", "")),
            "url": vuln.get("more_info_url", vuln.get("url", "")),
        }

    def _count_severity(self, severity: str, counts: dict[str, int]) -> None:
        """Increment severity count."""
        if severity in counts:
            counts[severity] += 1

    def get_type(self) -> str:
        """Get parser type name."""
        return "safety"


# Register the parser
register_parser("safety", SafetyParser)
