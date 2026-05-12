"""Parser for mypy type checker output."""

from __future__ import annotations

import re

from ci_tool.parsers import Parser, registry
from ci_tool.parsers.models import CodeSnippet, Issue, ParsedResult, Severity


class MypyParser(Parser):
    """Parser for mypy text output.

    Handles mypy's text format which includes:
    - Context lines (file.py: note: In ...)
    - Error lines (file.py:line:col:end_line:end_col: severity: message [code])
    - Source code and caret markers on following lines
    - Summary line (e.g. "Found 28 errors in 11 files (checked 155 source files)")

    Format examples:
        tools/ci/src/ci_tool/parsers/models.py: note: In class "ParsedResult":
        tools/ci/src/ci_tool/parsers/models.py:100:15:100:15: error: Missing type
        parameters for generic type "dict"  [type-arg]
                raw_data: dict = field(default_factory=dict)  # Original parsed da...
                  ^
        Found 28 errors in 11 files (checked 155 source files)
    """

    # Matches error/warning/note lines:
    # file:line:col:end_line:end_col: severity: message [code]
    #
    # Mypy outputs 4 position numbers: line, col, end_line, end_col
    # Example: src/foo.py:42:5:42:10: error: Type mismatch [assignment]
    ERROR_PATTERN = re.compile(
        r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):"
        r"(?P<end_line>\d+):(?P<end_col>\d+):\s*"
        r"(?P<severity>error|warning|note):\s*(?P<message>.+?)"
        r"(?:\s*\[(?P<error_code>[^\]]+)\])?$",
    )

    # Matches context lines: file.py: note: In ...
    # These provide location context (e.g. "In class X", "In method Y")
    # and precede the actual error line.
    CONTEXT_PATTERN = re.compile(
        r"^(?P<file>[^:]+):\s*note:\s*(?P<context>.+)$",
    )

    # Matches summary line: "Found N errors in M files (checked K source files)"
    SUMMARY_PATTERN = re.compile(
        r"^Found\s+(?P<total_errors>\d+)\s+errors?\s+in\s+(?P<files_with_errors>\d+)\s+files?"
        r"(?:\s*\(checked\s+(?P<total_files>\d+)\s+source\s+files?\))?$",
    )

    # Matches caret line: whitespace followed by ^
    CARET_PATTERN = re.compile(r"^\s+\^+\s*$")

    @property
    def name(self) -> str:
        return "mypy"

    @property
    def supported_filenames(self) -> list[str]:
        return ["mypy"]

    def parse(self, content: str, file_path: str = "") -> ParsedResult:
        result = ParsedResult(parser_name=self.name, file_path=file_path)
        issues: list[Issue] = []
        lines = content.strip().split("\n")

        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            i += 1

            # Skip empty lines
            if not line.strip():
                continue

            # Check for summary line (last line of mypy output)
            summary_match = self.SUMMARY_PATTERN.match(line.strip())
            if summary_match:
                result.raw_data["summary"] = summary_match.group(0)
                result.raw_data["total_errors_reported"] = int(
                    summary_match.group("total_errors")
                )
                continue

            # Check for context line (informational note about location)
            context = ""
            context_match = self.CONTEXT_PATTERN.match(line)
            if context_match:
                context = context_match.group("context")
                # Context lines are followed by the actual error line
                if i < len(lines):
                    line = lines[i].rstrip()
                    i += 1
                else:
                    continue

            # Parse error/warning/note line
            match = self.ERROR_PATTERN.match(line)
            if not match:
                continue

            f = match.group("file")
            severity_str = match.group("severity")
            error_code = match.group("error_code") or ""
            line_num = int(match.group("line"))
            col = int(match.group("col"))
            end_line = int(match.group("end_line"))
            end_col = int(match.group("end_col"))
            message = match.group("message").strip()

            # Determine severity and update counts
            if severity_str == "error":
                severity = Severity.ERROR
                result.errors += 1
            elif severity_str == "warning":
                severity = Severity.WARNING
                result.warnings += 1
            else:
                severity = Severity.NOTE
                # Notes are informational, don't count as passed/failed

            # Collect source code and caret lines that follow the error line.
            # Mypy outputs:
            #   1. Optional blank line
            #   2. Source code line(s) — indented, sometimes with ">" marker
            #   3. Caret line — whitespace + "^" (possibly multiple ^ for range)
            source_lines: list[str] = []

            while i < len(lines):
                next_line = lines[i]
                stripped = next_line.strip()

                # Empty line — could be between error and source, or between source and caret
                if not stripped:
                    i += 1
                    continue

                # Caret line — whitespace followed by ^ characters
                if self.CARET_PATTERN.match(next_line):
                    i += 1
                    break  # Caret line is always last in an error block

                # Source code line — starts with whitespace (indented)
                # or starts with ">" (mypy sometimes marks the error line)
                if next_line and next_line[0].isspace():
                    # Strip the leading ">" marker if present, keep the rest
                    cleaned = next_line
                    if cleaned.lstrip().startswith(">"):
                        # Remove the ">" marker and one space
                        indent = len(cleaned) - len(cleaned.lstrip())
                        cleaned = cleaned[:indent] + cleaned[indent:].lstrip()
                        if cleaned.startswith(" "):
                            cleaned = cleaned[1:]
                    source_lines.append(cleaned)
                    i += 1
                    continue

                # Anything else — next error, context, or summary — stop collecting
                break

            # Build source code snippet
            source = "\n".join(source_lines) if source_lines else ""
            if not source:
                # Try to read from the actual source file
                source = self._read_source_lines(f, line_num)

            snippet = None
            if source:
                snippet = CodeSnippet(
                    file_path=f,
                    line_number=line_num,
                    source=source,
                    column=col,
                    end_column=end_col,
                )

            # Build the full message
            full_message = message
            if error_code:
                full_message = f"{message} [{error_code}]"

            issues.append(
                Issue(
                    file_path=f,
                    line_number=line_num,
                    end_line_number=end_line,
                    column=col,
                    end_column=end_col,
                    severity=severity,
                    message=full_message,
                    rule_id=error_code,
                    rule_name=context or "",
                    code_snippet=snippet,
                )
            )

        result.total = len(issues)
        result.failed = result.errors
        result.issues = issues
        return result


registry.register(MypyParser())
