"""Data models for parsed results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    ERROR = "error"  # generic error
    WARNING = "warning"  # generic warning
    NOTE = "note"  # informational


@dataclass
class CodeSnippet:
    """A code snippet around an error location."""

    file_path: str
    line_number: int  # The error line (1-based)
    context_lines: int = 2  # Lines before and after (reduced for conciseness)
    source: str = ""  # The actual code content
    language: str = "python"  # For syntax highlighting in markdown
    column: int = 0  # Column number for precise error highlighting
    end_column: int = 0  # End column for range highlighting

    def render(self, max_lines: int = 8) -> str:
        """Render as a markdown code block in ty-style format.

        Uses a format similar to ty/rustc:
        - File path with line:column location
        - Arrow pointing to error location
        - Line numbers with pipe separator
        - Caret line showing error position
        """
        if not self.source:
            return ""
        lines = self.source.split("\n")
        # Filter out empty lines at the start
        while lines and not lines[0].strip():
            lines.pop(0)

        if len(lines) > max_lines:
            lines = lines[:max_lines]

        # Calculate starting line number for display
        start_line = max(1, self.line_number - self.context_lines)
        error_idx = self.line_number - start_line

        # Calculate the width needed for line numbers (for alignment)
        max_line_num = start_line + len(lines) - 1
        line_num_width = len(str(max_line_num))

        # Build the output
        parts = []
        col = self.column if self.column > 0 else 1
        parts.append(f"  --> {self.file_path}:{self.line_number}:{col}")
        parts.append("     |")

        for i, line in enumerate(lines):
            line_num = start_line + i
            line_num_str = str(line_num)
            if i == error_idx:
                # Error line - add caret pointing to column position
                parts.append(f"   {line_num_str:>{line_num_width}} | {line}")
                # Create caret at the right column position
                # The caret line needs to have the same prefix width as the error line
                # Prefix is "   " + line_num_str + " | " = 3 + len(line_num_str) + 2
                if self.column > 0 and self.column <= len(line):
                    # Caret should be at column position in the code
                    caret = " " * (self.column - 1) + "^"
                    if self.end_column > self.column:
                        caret = " " * (self.column - 1) + "^" * (
                            self.end_column - self.column
                        )
                    parts.append(
                        f"   {' ' * len(line_num_str):>{line_num_width}} | {caret}"
                    )
                else:
                    parts.append(
                        f"   {' ' * len(line_num_str):>{line_num_width}} | {'^' * min(len(line), 20)}"
                    )
            else:
                parts.append(f"   {line_num_str:>{line_num_width}} | {line}")

        return "```" + self.language + "\n" + "\n".join(parts) + "\n```"


@dataclass
class Issue:
    """A single issue found by a parser."""

    file_path: str
    line_number: int
    end_line_number: int = 0
    column: int = 0
    end_column: int = 0
    severity: Severity = Severity.ERROR
    message: str = ""
    rule_id: str = ""  # e.g. "F401", "B101", "arg-type"
    rule_name: str = ""  # e.g. "unused-import", "assert_used"
    code_snippet: CodeSnippet | None = None

    # For security scanners
    package: str = ""
    installed_version: str = ""
    fixed_version: str = ""
    cve_id: str = ""
    title: str = ""


@dataclass
class ParsedResult:
    """Complete result from parsing a report file."""

    parser_name: str
    file_path: str

    # Summary counts
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    warnings: int = 0
    skipped: int = 0
    duration_seconds: float = 0.0

    # For security scanners
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0

    # Detailed issues
    issues: list[Issue] = field(default_factory=list)

    # Metadata
    packages_scanned: int = 0
    raw_data: dict = field(default_factory=dict)  # Original parsed data

    # Error handling
    parse_error: str = ""

    @property
    def has_failures(self) -> bool:
        return self.failed > 0 or self.errors > 0

    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0

    @property
    def worst_severity(self) -> Severity:
        """Return the worst severity found."""
        if self.critical > 0 or any(
            i.severity == Severity.CRITICAL for i in self.issues
        ):
            return Severity.CRITICAL
        if self.high > 0 or any(i.severity == Severity.HIGH for i in self.issues):
            return Severity.HIGH
        if self.medium > 0 or any(i.severity == Severity.MEDIUM for i in self.issues):
            return Severity.MEDIUM
        if self.low > 0 or any(i.severity == Severity.LOW for i in self.issues):
            return Severity.LOW
        if self.has_failures:
            return Severity.ERROR
        return Severity.INFO

    def summary_line(self) -> str:
        """One-line summary for the job status table."""
        parts = []
        if self.passed > 0:
            parts.append(f"{self.passed} passed")
        if self.failed > 0:
            parts.append(f"{self.failed} failed")
        if self.errors > 0 and self.failed == 0:
            parts.append(f"{self.errors} errors")
        if self.warnings > 0:
            parts.append(f"{self.warnings} warnings")
        if self.skipped > 0:
            parts.append(f"{self.skipped} skipped")
        if self.critical > 0:
            parts.append(f"{self.critical} critical")
        if self.high > 0 and self.critical == 0:
            parts.append(f"{self.high} high")
        if not parts:
            return "no issues"
        return ", ".join(parts)
