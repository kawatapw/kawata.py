"""Parser for ty type checker JUnit XML results."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ci_tool.parsers import Parser, registry
from ci_tool.parsers.models import CodeSnippet, Issue, ParsedResult, Severity

try:
    from defusedxml.ElementTree import fromstring as safe_fromstring
except ImportError:
    safe_fromstring = ET.fromstring  # type: ignore[assignment]

# ty failure messages repeat "line N, col M, ..." at the start.
# Strip that prefix since line/column are already displayed separately.
_LINE_COL_PREFIX = re.compile(r"^line \d+, col \d+,\s*")


class TyParser(Parser):
    """Parser for ty type checker JUnit XML output.

    ty's JUnit XML format uses:
      - <testsuites> root with per-file <testsuite> children
      - <testcase> with name="org.ty.<rule>", classname="<file_path>", line="N", column="N"
      - <failure message="short message">full error text</failure>

    Quirks handled:
      - classname omits the ``.py`` extension (restored here).
      - classname is an absolute path (made relative to the project root).
      - failure text repeats "line N, col M, ..." (stripped for display).
    """

    @property
    def name(self) -> str:
        return "ty"

    @property
    def supported_extensions(self) -> list[str]:
        return [".xml"]

    @property
    def supported_filenames(self) -> list[str]:
        return ["ty"]

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _restore_extension(file_path: str) -> str:
        """ty's classname attribute strips the ``.py`` extension.

        If *file_path* has no suffix and appending ``.py`` yields an existing
        file, the extension is restored.  Otherwise the path is returned as-is.
        """
        p = Path(file_path)
        if p.suffix == "":
            candidate = p.with_suffix(".py")
            if candidate.exists():
                return str(candidate)
        return file_path

    @staticmethod
    def _make_relative(file_path: str) -> str:
        """Convert an absolute path to one relative to the project root (cwd)."""
        p = Path(file_path)
        if p.is_absolute():
            try:
                return str(p.relative_to(Path.cwd()))
            except ValueError:
                pass  # not under cwd – return as-is
        return file_path

    @staticmethod
    def _clean_message(raw: str) -> str:
        """Strip the redundant 'line N, col M, ' prefix from ty messages."""
        return _LINE_COL_PREFIX.sub("", raw)

    # -- parsing --------------------------------------------------------------

    def parse(self, content: str, file_path: str = "") -> ParsedResult:
        result = ParsedResult(parser_name=self.name, file_path=file_path)

        if not content.strip():
            return result

        try:
            root = safe_fromstring(content)
        except ET.ParseError as e:
            result.parse_error = f"XML parse error: {e}"
            return result

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
                failure = tc.find("failure")
                if failure is not None:
                    tc_file = tc.get("classname", "")
                    tc_line = int(tc.get("line", 0))
                    tc_column = int(tc.get("column", 0))

                    # Fix 1: restore the .py extension ty strips from classname
                    tc_file = self._restore_extension(tc_file)

                    # Fix 2: make absolute paths relative to cwd
                    tc_file = self._make_relative(tc_file)

                    # Fix 3: clean redundant line/col prefix from message
                    raw_message = (failure.text or "").strip() or failure.get(
                        "message", ""
                    )
                    message = self._clean_message(raw_message)

                    # Extract rule ID from testcase name (e.g. "org.ty.unresolved-reference")
                    rule_id = ""
                    tc_name = tc.get("name", "")
                    if tc_name.startswith("org.ty."):
                        rule_id = tc_name[len("org.ty.") :]

                    snippet = None
                    if tc_file and tc_line > 0:
                        source = self._read_source_lines(tc_file, tc_line)
                        if source:
                            snippet = CodeSnippet(
                                file_path=tc_file,
                                line_number=tc_line,
                                source=source,
                            )

                    issues.append(
                        Issue(
                            file_path=tc_file,
                            line_number=tc_line,
                            column=tc_column,
                            severity=Severity.ERROR,
                            message=message,
                            rule_id=rule_id,
                            code_snippet=snippet,
                        )
                    )

        result.passed = result.total - result.failed - result.errors - result.skipped
        result.issues = issues
        return result


registry.register(TyParser())
