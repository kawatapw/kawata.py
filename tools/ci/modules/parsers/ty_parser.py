"""Ty type checker parser."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from defusedxml.ElementTree import fromstring as safe_fromstring

from .registry import Parser
from .registry import register_parser

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET


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

        # Coderabbit: aggregate counters across every <testsuite> when the
        # root is <testsuites>. Reading only the first child caused the
        # summary totals to disagree with the test_cases list (which is
        # already collected from the whole tree below). Falls back to
        # treating root itself as a single testsuite when the root tag
        # is not <testsuites>.
        summary = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "duration": 0.0,
        }

        if root.tag == "testsuites":
            suites: list[ET.Element] = root.findall("testsuite")
        else:
            suites = [root]

        for suite in suites:
            summary["total"] += int(suite.get("tests", 0))
            summary["passed"] += int(suite.get("passed", 0))
            summary["failed"] += int(suite.get("failures", 0))
            summary["skipped"] += int(suite.get("skipped", 0))
            summary["errors"] += int(suite.get("errors", 0))
            summary["duration"] += float(suite.get("time", 0))

        # If passed is not in the XML, calculate it from total minus the other buckets
        # (failed + skipped + errors). Previously omitted errors, which inflated passed.
        if summary["passed"] == 0 and summary["total"] > 0:
            summary["passed"] = (
                summary["total"]
                - summary["failed"]
                - summary["skipped"]
                - summary.get("errors", 0)
            )

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
