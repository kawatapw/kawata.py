"""Trivy vulnerability scanner parser."""

from __future__ import annotations

import json
from typing import Any

from .registry import Parser
from .registry import register_parser


class TrivyParser(Parser):
    """Parser for Trivy vulnerability scanner output (SARIF and JSON formats)."""

    def parse(self, content: str) -> dict[str, Any]:
        """Parse Trivy output content (auto-detects SARIF or JSON)."""
        data = json.loads(content)

        # Detect format
        if "$schema" in data and "sarif" in data.get("$schema", "").lower():
            return self._parse_sarif(data)
        if "Results" in data or "results" in data:
            return self._parse_json(data)
        # Try to parse as generic JSON
        return self._parse_json(data)

    def _parse_sarif(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse Trivy SARIF output."""
        vulnerabilities: list[dict[str, Any]] = []
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}

        runs = data.get("runs", [])
        for run in runs:
            results = run.get("results", [])
            for result in results:
                rule_id = result.get("ruleId", "")
                level = result.get("level", "warning")
                message = result.get("message", {}).get("text", "")
                locations = result.get("locations", [])

                # Map SARIF level to severity
                severity = self._map_sarif_level(level)

                # Extract package info from locations if available
                package = ""
                installed_version = ""
                fixed_version = ""

                if locations:
                    physical_location = locations[0].get("physicalLocation", {})
                    artifact_location = physical_location.get("artifactLocation", {})
                    package = artifact_location.get("uri", "")

                # Try to extract CVE ID from rule_id
                cve_id = rule_id if rule_id.startswith("CVE-") else ""

                vulnerability = {
                    "id": cve_id or rule_id,
                    "severity": severity,
                    "package": package,
                    "installed_version": installed_version,
                    "fixed_version": fixed_version or None,
                    "title": rule_id,
                    "description": message,
                    "url": "",
                }

                vulnerabilities.append(vulnerability)

                # Count severities
                if severity in severity_counts:
                    severity_counts[severity] += 1

        return {
            "type": "trivy",
            "summary": {
                "total_vulnerabilities": len(vulnerabilities),
                **severity_counts,
            },
            "vulnerabilities": vulnerabilities,
        }

    def _parse_json(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse Trivy JSON output."""
        vulnerabilities: list[dict[str, Any]] = []
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}

        # Handle different JSON structures
        results = data.get("Results", data.get("results", []))

        for result in results:
            target = result.get("Target", result.get("target", ""))
            vulns = result.get("Vulnerabilities", result.get("vulnerabilities", []))

            for vuln in vulns:
                vuln_id = vuln.get("VulnerabilityID", vuln.get("id", ""))
                severity = vuln.get("Severity", vuln.get("severity", "UNKNOWN")).lower()
                pkg_name = vuln.get("PkgName", vuln.get("package", ""))
                installed_version = vuln.get(
                    "InstalledVersion",
                    vuln.get("installed_version", ""),
                )
                fixed_version = vuln.get("FixedVersion", vuln.get("fixed_version", ""))
                title = vuln.get("Title", vuln.get("title", ""))
                description = vuln.get("Description", vuln.get("description", ""))
                references = vuln.get("References", vuln.get("references", []))

                # Get URL from references
                url = ""
                if references and isinstance(references, list) and len(references) > 0:
                    url = references[0] if isinstance(references[0], str) else ""

                vulnerability = {
                    "id": vuln_id,
                    "severity": severity,
                    "package": pkg_name,
                    "installed_version": installed_version,
                    "fixed_version": fixed_version or None,
                    "title": title,
                    "description": description,
                    "url": url,
                    "target": target,
                }

                vulnerabilities.append(vulnerability)

                # Count severities
                if severity in severity_counts:
                    severity_counts[severity] += 1

        return {
            "type": "trivy",
            "summary": {
                "total_vulnerabilities": len(vulnerabilities),
                **severity_counts,
            },
            "vulnerabilities": vulnerabilities,
        }

    def _map_sarif_level(self, level: str) -> str:
        """Map SARIF level to severity string."""
        level_map = {
            "error": "critical",
            "warning": "high",
            "note": "medium",
            "info": "low",
        }
        return level_map.get(level.lower(), "info")

    def get_type(self) -> str:
        """Get parser type name."""
        return "trivy"


# Register the parser
register_parser("trivy", TrivyParser)
