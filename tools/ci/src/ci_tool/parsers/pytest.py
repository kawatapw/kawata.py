"""Parser for pytest JUnit XML results."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from ci_tool.parsers import Parser, registry
from ci_tool.parsers.models import CodeSnippet, Issue, ParsedResult, Severity

try:
    from defusedxml.ElementTree import fromstring as safe_fromstring
except ImportError:
    safe_fromstring = ET.fromstring  # type: ignore[assignment]


class PytestParser(Parser):
    """Parser for pytest JUnit XML output."""

    @property
    def name(self) -> str:
        return "pytest"

    @property
    def supported_extensions(self) -> list[str]:
        return [".xml"]

    @property
    def supported_filenames(self) -> list[str]:
        return ["junit", "pytest", "test-results"]

    def parse(self, content: str, file_path: str = "") -> ParsedResult:
        result = ParsedResult(parser_name=self.name, file_path=file_path)

        try:
            root = safe_fromstring(content)
        except ET.ParseError as e:
            result.parse_error = f"XML parse error: {e}"
            return result

        # Handle both <testsuites> and <testsuite> root
        if root.tag == "testsuites":
            suites = root.findall("testsuite")
        else:
            suites = [root]

        issues: list[Issue] = []
        for suite in suites:
            result.total += int(suite.get("tests", 0))
            result.failed += int(suite.get("failures", 0))
            result.errors += int(suite.get("errors", 0))
            result.skipped += int(suite.get("skipped", 0))
            result.duration_seconds += float(suite.get("time", 0))

            for tc in suite.findall("testcase"):
                # Handle both <failure> and <error> elements (both represent failures)
                failure = tc.find("failure")
                error = tc.find("error")
                issue_elem = failure if failure is not None else error

                if issue_elem is not None:
                    classname = tc.get("classname", "")
                    name = tc.get("name", "")
                    tc_file = tc.get("file", "")
                    tc_line = int(tc.get("line", 0))
                    message = issue_elem.get("message", "")

                    # For collection errors, extract file/line from the error text
                    if not tc_file and not tc_line:
                        tc_file, tc_line = self._extract_location_from_error(
                            issue_elem.text or ""
                        )

                    snippet = None
                    if tc_file and tc_line > 0:
                        source = self._read_source_lines(tc_file, tc_line)
                        if source:
                            snippet = CodeSnippet(
                                file_path=tc_file,
                                line_number=tc_line,
                                source=source,
                            )

                    # Build a cleaner message
                    test_name = f"{classname}.{name}" if classname else name
                    full_message = f"{test_name}: {message}" if message else test_name

                    issues.append(
                        Issue(
                            file_path=tc_file or classname or "unknown",
                            line_number=tc_line or 0,
                            severity=Severity.ERROR,
                            message=full_message,
                            code_snippet=snippet,
                        )
                    )

        result.passed = result.total - result.failed - result.errors - result.skipped
        result.issues = issues
        return result

    def _extract_location_from_error(self, error_text: str) -> tuple[str, int]:
        """Extract file path and line number from pytest error text.

        For collection errors, the error text contains lines like:
        tests/unit/ci/test_ci_context.py:12: in module
        """
        import html
        import re

        # Unescape HTML entities (pytest may escape < and >)
        text = html.unescape(error_text)

        # Pattern: file.py:line: or file.py:line in
        # Look for test file paths first (tests/, test_ prefix), then fall back to any .py file
        matches = list(re.finditer(r"^(.+\.py):(\d+)", text, re.MULTILINE))
        for match in matches:
            path = match.group(1)
            # Prefer test files over stdlib paths
            if "tests/" in path or path.endswith("test_") or "test_" in path:
                return path, int(match.group(2))

        # Fall back to first match if no test file found
        if matches:
            return matches[0].group(1), int(matches[0].group(2))
        return "", 0


# Auto-register
registry.register(PytestParser())
