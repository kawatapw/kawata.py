"""Ty type checker parser."""

import xml.etree.ElementTree as ET
from typing import Any

from defusedxml.ElementTree import fromstring as safe_fromstring

from .registry import Parser, register_parser


class TyParser(Parser):
    """Parser for Ty type checker JUnit XML results."""

    def parse(self, content: str) -> dict[str, Any]:
        """Parse Ty JUnit XML content."""
        # Handle empty content
        if not content.strip():
            return {
                "type": "ty",
                "summary": {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "errors": 0,
                    "duration": 0.0,
                },
                "test_cases": [],
            }

        root = safe_fromstring(content)

        # Find the testsuite element (may be root or nested)
        testsuite: ET.Element = root
        if root.tag == "testsuites":
            # Root is testsuites, find first testsuite
            found = root.find("testsuite")
            if found is not None:
                testsuite = found

        # Extract test summary
        summary = {
            "total": int(testsuite.get("tests", 0)),
            "passed": int(testsuite.get("passed", 0)),
            "failed": int(testsuite.get("failures", 0)),
            "skipped": int(testsuite.get("skipped", 0)),
            "errors": int(testsuite.get("errors", 0)),
            "duration": float(testsuite.get("time", 0)),
        }

        # If passed is not in the XML, calculate it from total, failed, and skipped
        if summary["passed"] == 0 and summary["total"] > 0:
            summary["passed"] = summary["total"] - summary["failed"] - summary["skipped"]

        # Extract test cases (type errors)
        test_cases = []
        for testcase in root.findall(".//testcase"):
            test_case = {
                "name": testcase.get("name"),
                "classname": testcase.get("classname"),
                "file": testcase.get("file"),
                "line": int(testcase.get("line", 0)),
                "duration": float(testcase.get("time", 0)),
            }

            # Check for failures (type errors)
            failure = testcase.find("failure")
            if failure is not None:
                test_case["status"] = "failed"
                test_case["message"] = failure.get("message", "")
                test_case["type"] = failure.get("type", "")
            else:
                test_case["status"] = "passed"

            test_cases.append(test_case)

        return {"type": "ty", "summary": summary, "test_cases": test_cases}

    def get_type(self) -> str:
        """Get parser type name."""
        return "ty"


# Register the parser
register_parser("ty", TyParser)