# Phase 2 — Parser Plugin System

## Scope

Plugin-based parser system for reading test/lint/security output files and producing structured, typed result data. All parsers are plugins — built-in ones ship with the tool, custom ones load from config.

## 1. Design Principles

1. **Every parser is a plugin** — Built-in parsers are just plugins that ship by default. No special treatment in code.
2. **Typed output** — Every parser returns a `ParsedResult` with structured data, not raw dicts.
3. **Auto-detection** — Parsers self-identify which files they can handle via filename patterns, extensions, and content sniffing.
4. **Graceful degradation** — If a parser fails, it returns a result with error info rather than raising.
5. **Code snippet extraction** — Parsers that support it (ruff, mypy, ty, pytest) extract code context around errors for display in collapsible sections.

## 2. Parser Models

### `src/ci_tool/parsers/models.py`

```python
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
    ERROR = "error"       # generic error
    WARNING = "warning"   # generic warning
    NOTE = "note"         # informational


@dataclass
class CodeSnippet:
    """A code snippet around an error location."""
    file_path: str
    line_number: int              # The error line (1-based)
    context_lines: int = 4        # Lines before and after
    source: str = ""              # The actual code content
    language: str = "python"      # For syntax highlighting in markdown

    def render(self, max_lines: int = 8) -> str:
        """Render as a markdown code block with line numbers."""
        if not self.source:
            return ""
        lines = self.source.split("\n")
        if len(lines) > max_lines:
            # Keep the error line visible, trim around it
            lines = lines[:max_lines]

        # Calculate starting line number for display
        start_line = max(1, self.line_number - self.context_lines)
        formatted = []
        for i, line in enumerate(lines):
            line_num = start_line + i
            marker = ">" if line_num == self.line_number else " "
            formatted.append(f"  {line_num:>4} | {marker}{line}")

        return f"```{self.language}\n" + "\n".join(formatted) + "\n```"


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
    rule_id: str = ""          # e.g. "F401", "B101", "arg-type"
    rule_name: str = ""        # e.g. "unused-import", "assert_used"
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
    raw_data: dict = field(default_factory=dict)  # Original parsed data for custom formatters

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
        if self.critical > 0 or any(i.severity == Severity.CRITICAL for i in self.issues):
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
```

## 3. Parser Base Class & Registry

### `src/ci_tool/parsers/__init__.py`

```python
"""Parser plugin system."""

from __future__ import annotations

import importlib
import pkgutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Type

from ci_tool.parsers.models import ParsedResult


class Parser(ABC):
    """Base class for all parsers.

    Every parser is a plugin. It must implement:
      - name: unique identifier
      - supported_extensions: file extensions it can handle
      - supported_filenames: filename substrings it can match
      - parse(): actual parsing logic
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique parser identifier (e.g. 'pytest', 'ruff')."""

    @property
    def supported_extensions(self) -> list[str]:
        """File extensions this parser can handle. Empty = any."""
        return []

    @property
    def supported_filenames(self) -> list[str]:
        """Filename substrings this parser can match."""
        return []

    @abstractmethod
    def parse(self, content: str, file_path: str = "") -> ParsedResult:
        """Parse file content and return structured result.

        Args:
            content: Raw file content as string.
            file_path: Original file path (for error messages and code snippet loading).

        Returns:
            ParsedResult with structured data. On failure, set parse_error
            and return a partial result rather than raising.
        """

    def can_parse(self, file_path: str, content: str = "") -> bool:
        """Check if this parser can handle the given file."""
        path = Path(file_path)
        filename = path.name.lower()
        suffix = path.suffix.lower()

        # Check filename patterns
        for pattern in self.supported_filenames:
            if pattern.lower() in filename:
                return True

        # Check extensions
        if self.supported_extensions and suffix in self.supported_extensions:
            return True

        # If no specific patterns, this is a generic parser
        if not self.supported_filenames and not self.supported_extensions:
            return True

        return False

    def _read_source_lines(
        self, file_path: str, error_line: int, context: int = 4
    ) -> str:
        """Read source code around an error line for code snippets.

        Args:
            file_path: Path to the source file.
            error_line: 1-based line number of the error.
            context: Number of lines before and after to include.

        Returns:
            Source code string, or empty string if file not found.
        """
        if not file_path:
            return ""
        try:
            path = Path(file_path)
            if not path.is_absolute():
                # Try relative to cwd
                path = Path.cwd() / path
            if not path.exists():
                return ""
            lines = path.read_text(encoding="utf-8", errors="replace").split("\n")
            start = max(0, error_line - context - 1)
            end = min(len(lines), error_line + context)
            return "\n".join(lines[start:end])
        except Exception:
            return ""


class ParserRegistry:
    """Registry for parser plugins.

    Supports:
      - Auto-discovery of built-in parsers
      - Manual registration of custom parsers
      - Auto-detection of the right parser for a file
    """

    def __init__(self) -> None:
        self._parsers: dict[str, Parser] = {}

    def register(self, parser: Parser) -> None:
        """Register a parser instance."""
        self._parsers[parser.name] = parser

    def get(self, name: str) -> Parser:
        """Get a parser by name."""
        if name not in self._parsers:
            available = ", ".join(sorted(self._parsers.keys()))
            raise KeyError(
                f"Unknown parser: '{name}'. Available: {available}"
            )
        return self._parsers[name]

    def detect(self, file_path: str, content: str = "") -> Parser:
        """Auto-detect the best parser for a file.

        Strategy:
        1. Check filename patterns (most specific)
        2. Check file extensions
        3. For JSON files, inspect content structure
        4. Fall back to generic parser
        """
        # First pass: filename matching (most reliable)
        for parser in self._parsers.values():
            if parser.supported_filenames:
                path = Path(file_path)
                filename = path.name.lower()
                for pattern in parser.supported_filenames:
                    if pattern.lower() in filename:
                        return parser

        # Second pass: extension matching
        path = Path(file_path)
        suffix = path.suffix.lower()
        for parser in self._parsers.values():
            if parser.supported_extensions and suffix in parser.supported_extensions:
                return parser

        # Third pass: content-based detection for JSON
        if suffix == ".json" and content:
            return self._detect_json_parser(content)

        # Fall back to generic
        if "generic" in self._parsers:
            return self._parsers["generic"]

        raise KeyError(f"No parser found for: {file_path}")

    def _detect_json_parser(self, content: str) -> Parser:
        """Inspect JSON content to determine the right parser."""
        import json
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return self._parsers.get("generic", list(self._parsers.values())[0])

        if isinstance(data, dict):
            # SARIF format -> trivy
            schema = data.get("$schema", "")
            if "sarif" in schema.lower():
                return self._parsers.get("trivy", self._parsers["generic"])

            # Trivy JSON
            if "Results" in data or "results" in data:
                return self._parsers.get("trivy", self._parsers["generic"])

            # Safety
            if "vulnerabilities" in data or "scanned_packages" in data:
                return self._parsers.get("safety", self._parsers["generic"])

            # Bandit
            if "results" in data and "metrics" in data:
                return self._parsers.get("bandit", self._parsers["generic"])

        # Ruff JSON (array of violations)
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            if isinstance(first, dict) and ("code" in first or "rule_code" in first):
                return self._parsers.get("ruff", self._parsers["generic"])

        return self._parsers.get("generic", list(self._parsers.values())[0])

    def list_parsers(self) -> list[str]:
        """List all registered parser names."""
        return sorted(self._parsers.keys())

    def load_builtin_parsers(self) -> None:
        """Auto-discover and register all built-in parser plugins."""
        # Import all modules in the parsers package to trigger registration
        package_dir = Path(__file__).parent
        for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
            if module_name in ("models",):
                continue
            importlib.import_module(f"ci_tool.parsers.{module_name}")


# Global registry instance
registry = ParserRegistry()
```

## 4. Built-in Parsers

### `src/ci_tool/parsers/pytest.py`

```python
"""Parser for pytest JUnit XML results."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

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
                failure = tc.find("failure")
                if failure is not None:
                    classname = tc.get("classname", "")
                    name = tc.get("name", "")
                    tc_file = tc.get("file", "")
                    tc_line = int(tc.get("line", 0))
                    message = failure.get("message", "")

                    snippet = None
                    if tc_file and tc_line > 0:
                        source = self._read_source_lines(tc_file, tc_line)
                        if source:
                            snippet = CodeSnippet(
                                file_path=tc_file,
                                line_number=tc_line,
                                source=source,
                            )

                    issues.append(Issue(
                        file_path=tc_file or classname,
                        line_number=tc_line,
                        severity=Severity.ERROR,
                        message=f"{classname}.{name}: {message}",
                        code_snippet=snippet,
                    ))

        result.passed = result.total - result.failed - result.errors - result.skipped
        result.issues = issues
        return result


# Auto-register
registry.register(PytestParser())
```

### `src/ci_tool/parsers/mypy.py`

```python
"""Parser for mypy type checker output."""

from __future__ import annotations

import re
from pathlib import Path

from ci_tool.parsers import Parser, registry
from ci_tool.parsers.models import CodeSnippet, Issue, ParsedResult, Severity


class MypyParser(Parser):
    """Parser for mypy text output.

    Format: path/to/file.py:line: severity: Message [error-code]
    """

    PATTERN = re.compile(
        r"^(?P<file>[^:]+):(?P<line>\d+):(?:(?P<end_line>\d+):)?\s*"
        r"(?P<severity>error|note|warning):\s*(?P<message>.+?)"
        r"(?:\s*\[(?P<error_code>[^\]]+)\])?$",
    )

    @property
    def name(self) -> str:
        return "mypy"

    @property
    def supported_filenames(self) -> list[str]:
        return ["mypy"]

    def parse(self, content: str, file_path: str = "") -> ParsedResult:
        result = ParsedResult(parser_name=self.name, file_path=file_path)
        issues: list[Issue] = []
        files_with_errors: set[str] = set()

        for line in content.strip().split("\n"):
            if not line.strip():
                continue

            match = self.PATTERN.match(line)
            if not match:
                continue

            f = match.group("file")
            severity_str = match.group("severity")
            error_code = match.group("error_code") or ""
            line_num = int(match.group("line"))
            message = match.group("message").strip()

            severity = Severity.ERROR if severity_str == "error" else (
                Severity.WARNING if severity_str == "warning" else Severity.NOTE
            )

            if severity == Severity.ERROR:
                result.errors += 1
                files_with_errors.add(f)
            elif severity == Severity.WARNING:
                result.warnings += 1
            else:
                result.passed += 1  # notes are informational

            snippet = None
            source = self._read_source_lines(f, line_num)
            if source:
                snippet = CodeSnippet(
                    file_path=f,
                    line_number=line_num,
                    source=source,
                )

            issues.append(Issue(
                file_path=f,
                line_number=line_num,
                severity=severity,
                message=f"{message} [{error_code}]" if error_code else message,
                rule_id=error_code,
                code_snippet=snippet,
            ))

        result.total = len(issues)
        result.issues = issues
        return result


registry.register(MypyParser())
```

### `src/ci_tool/parsers/ruff.py`

```python
"""Parser for ruff linter output (text and JSON)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ci_tool.parsers import Parser, registry
from ci_tool.parsers.models import CodeSnippet, Issue, ParsedResult, Severity


class RuffParser(Parser):
    """Parser for ruff text and JSON output."""

    TEXT_PATTERN = re.compile(
        r"^(?P<file>[^:]+):(?P<line>\d+):(?P<column>\d+):\s*"
        r"(?P<rule_code>[A-Z]+\d+)\s+(?P<message>.+)$",
    )

    @property
    def name(self) -> str:
        return "ruff"

    @property
    def supported_filenames(self) -> list[str]:
        return ["ruff"]

    def parse(self, content: str, file_path: str = "") -> ParsedResult:
        content = content.strip()

        # Try JSON first
        if content.startswith("[") or content.startswith("{"):
            try:
                data = json.loads(content)
                return self._parse_json(data, file_path)
            except json.JSONDecodeError:
                pass

        return self._parse_text(content, file_path)

    def _parse_json(
        self, data: list | dict, file_path: str
    ) -> ParsedResult:
        result = ParsedResult(parser_name=self.name, file_path=file_path)
        issues: list[Issue] = []

        items = data if isinstance(data, list) else data.get("violations", [])

        for item in items:
            rule_code = item.get("code", item.get("rule_code", ""))
            location = item.get("location", {})
            end_location = item.get("end_location", {})
            row = location.get("row", 0)
            col = location.get("column", 0)

            snippet = None
            fname = item.get("filename", "")
            if fname and row > 0:
                source = self._read_source_lines(fname, row)
                if source:
                    snippet = CodeSnippet(
                        file_path=fname,
                        line_number=row,
                        source=source,
                    )

            issues.append(Issue(
                file_path=fname,
                line_number=row,
                column=col,
                end_line_number=end_location.get("row", 0),
                end_column=end_location.get("column", 0),
                severity=Severity.ERROR,
                message=item.get("message", ""),
                rule_id=rule_code,
                code_snippet=snippet,
            ))

        result.errors = len(issues)
        result.issues = issues
        return result

    def _parse_text(self, content: str, file_path: str) -> ParsedResult:
        result = ParsedResult(parser_name=self.name, file_path=file_path)
        issues: list[Issue] = []

        for line in content.split("\n"):
            if not line.strip():
                continue

            match = self.TEXT_PATTERN.match(line)
            if not match:
                continue

            fname = match.group("file")
            line_num = int(match.group("line"))
            rule_code = match.group("rule_code")

            snippet = None
            source = self._read_source_lines(fname, line_num)
            if source:
                snippet = CodeSnippet(
                    file_path=fname,
                    line_number=line_num,
                    source=source,
                )

            issues.append(Issue(
                file_path=fname,
                line_number=line_num,
                column=int(match.group("column")),
                severity=Severity.ERROR,
                message=match.group("message").strip(),
                rule_id=rule_code,
                code_snippet=snippet,
            ))

        result.errors = len(issues)
        result.issues = issues
        return result


registry.register(RuffParser())
```

### `src/ci_tool/parsers/ty.py`

```python
"""Parser for ty type checker JUnit XML results."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ci_tool.parsers import Parser, registry
from ci_tool.parsers.models import CodeSnippet, Issue, ParsedResult, Severity

try:
    from defusedxml.ElementTree import fromstring as safe_fromstring
except ImportError:
    safe_fromstring = ET.fromstring  # type: ignore[assignment]


class TyParser(Parser):
    """Parser for ty type checker JUnit XML output."""

    @property
    def name(self) -> str:
        return "ty"

    @property
    def supported_extensions(self) -> list[str]:
        return [".xml"]

    @property
    def supported_filenames(self) -> list[str]:
        return ["ty"]

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
                    tc_file = tc.get("file", "")
                    tc_line = int(tc.get("line", 0))
                    message = failure.get("message", "")

                    snippet = None
                    if tc_file and tc_line > 0:
                        source = self._read_source_lines(tc_file, tc_line)
                        if source:
                            snippet = CodeSnippet(
                                file_path=tc_file,
                                line_number=tc_line,
                                source=source,
                            )

                    issues.append(Issue(
                        file_path=tc_file,
                        line_number=tc_line,
                        severity=Severity.ERROR,
                        message=message,
                        code_snippet=snippet,
                    ))

        result.passed = result.total - result.failed - result.errors - result.skipped
        result.issues = issues
        return result


registry.register(TyParser())
```

### `src/ci_tool/parsers/bandit.py`

```python
"""Parser for bandit security scanner JSON output."""

from __future__ import annotations

import json
from pathlib import Path

from ci_tool.parsers import Parser, registry
from ci_tool.parsers.models import Issue, ParsedResult, Severity


class BanditParser(Parser):
    """Parser for bandit JSON output."""

    SEVERITY_MAP = {
        "HIGH": Severity.HIGH,
        "MEDIUM": Severity.MEDIUM,
        "LOW": Severity.LOW,
    }

    @property
    def name(self) -> str:
        return "bandit"

    @property
    def supported_filenames(self) -> list[str]:
        return ["bandit"]

    def parse(self, content: str, file_path: str = "") -> ParsedResult:
        result = ParsedResult(parser_name=self.name, file_path=file_path)

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            result.parse_error = f"JSON parse error: {e}"
            return result

        metrics = data.get("metrics", {})
        result.total = metrics.get("total", 0)
        result.high = metrics.get("SEVERITY.HIGH", 0)
        result.medium = metrics.get("SEVERITY.MEDIUM", 0)
        result.low = metrics.get("SEVERITY.LOW", 0)

        issues: list[Issue] = []
        for item in data.get("results", []):
            severity_str = item.get("issue_severity", "LOW")
            sev = self.SEVERITY_MAP.get(severity_str, Severity.LOW)

            issues.append(Issue(
                file_path=item.get("filename", ""),
                line_number=item.get("line_number", 0),
                severity=sev,
                message=item.get("issue_text", ""),
                rule_id=item.get("test_id", ""),
                rule_name=item.get("test_name", ""),
            ))

        result.issues = issues
        return result


registry.register(BanditParser())
```

### `src/ci_tool/parsers/trivy.py`

```python
"""Parser for trivy vulnerability scanner (SARIF and JSON)."""

from __future__ import annotations

import json
from pathlib import Path

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

                issues.append(Issue(
                    file_path="",
                    line_number=0,
                    severity=severity,
                    message=r.get("message", {}).get("text", ""),
                    rule_id=rule_id,
                    cve_id=cve_id,
                ))

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

                issues.append(Issue(
                    file_path="",
                    line_number=0,
                    severity=severity,
                    message=vuln.get("Title", vuln.get("title", "")),
                    rule_id=vuln.get("VulnerabilityID", vuln.get("id", "")),
                    package=vuln.get("PkgName", vuln.get("package", "")),
                    installed_version=vuln.get("InstalledVersion", ""),
                    fixed_version=vuln.get("FixedVersion", ""),
                ))

        result.total = len(issues)
        result.issues = issues
        return result


registry.register(TrivyParser())
```

### `src/ci_tool/parsers/safety.py`

```python
"""Parser for safety dependency vulnerability scanner."""

from __future__ import annotations

import json
import re
from pathlib import Path

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

    def _parse_vulnerability(
        self, vuln: dict, package_name: str = ""
    ) -> Issue:
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
```

### `src/ci_tool/parsers/generic.py`

```python
"""Generic fallback parser for unrecognized file types."""

from __future__ import annotations

import json
from pathlib import Path

from ci_tool.parsers import Parser, registry
from ci_tool.parsers.models import ParsedResult


class GenericParser(Parser):
    """Fallback parser that tries JSON, then returns raw text info."""

    @property
    def name(self) -> str:
        return "generic"

    def parse(self, content: str, file_path: str = "") -> ParsedResult:
        result = ParsedResult(parser_name=self.name, file_path=file_path)

        try:
            data = json.loads(content)
            result.total = 1
            result.passed = 1
            result.raw_data = {"type": "json", "data": data}
        except json.JSONDecodeError:
            lines = content.split("\n")
            result.total = len(lines)
            result.passed = len(lines)
            result.raw_data = {"type": "text", "line_count": len(lines)}

        return result


registry.register(GenericParser())
```

## 5. Tests

### `tests/test_parsers.py`

```python
"""Tests for all parsers."""

from __future__ import annotations

import pytest

from ci_tool.parsers import registry
from ci_tool.parsers.models import Severity

# Ensure built-in parsers are loaded
registry.load_builtin_parsers()


class TestParserRegistry:
    def test_builtin_parsers_loaded(self) -> None:
        parsers = registry.list_parsers()
        assert "pytest" in parsers
        assert "mypy" in parsers
        assert "ruff" in parsers
        assert "ty" in parsers
        assert "bandit" in parsers
        assert "trivy" in parsers
        assert "safety" in parsers
        assert "generic" in parsers

    def test_detect_by_filename(self) -> None:
        assert registry.detect("mypy-output.txt").name == "mypy"
        assert registry.detect("ruff-results.json").name == "ruff"
        assert registry.detect("trivy-results.sarif").name == "trivy"
        assert registry.detect("safety-report.json").name == "safety"
        assert registry.detect("bandit-output.json").name == "bandit"
        assert registry.detect("junit.xml").name == "pytest"

    def test_detect_json_by_content(self) -> None:
        sarif = '{"$schema": "https://sarif-schema"}'
        assert registry.detect("report.json", sarif).name == "trivy"

        safety = '{"vulnerabilities": [], "scanned_packages": {}}'
        assert registry.detect("report.json", safety).name == "safety"

        bandit = '{"results": [], "metrics": {}}'
        assert registry.detect("report.json", bandit).name == "bandit"


class TestPytestParser:
    def _make_parser(self):
        return registry.get("pytest")

    def test_parse_junit_xml(self) -> None:
        content = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="10" errors="0" failures="1" skipped="2" time="5.5">
    <testcase classname="test_module" name="test_pass" time="0.1"/>
    <testcase classname="test_module" name="test_fail" time="0.2">
      <failure message="AssertionError">assert False</failure>
    </testcase>
  </testsuite>
</testsuites>"""
        result = self._make_parser().parse(content)
        assert result.total == 10
        assert result.failed == 1
        assert result.skipped == 2
        assert result.passed == 7
        assert len(result.issues) == 1
        assert result.issues[0].severity == Severity.ERROR

    def test_parse_empty(self) -> None:
        content = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="0" errors="0" failures="0" skipped="0" time="0"/>
</testsuites>"""
        result = self._make_parser().parse(content)
        assert result.total == 0
        assert not result.has_failures


class TestMypyParser:
    def _make_parser(self):
        return registry.get("mypy")

    def test_parse_errors(self) -> None:
        content = """\
app/main.py:10: error: Name "x" is not defined [name-defined]
app/main.py:15: error: Argument 1 has incompatible type "str"; expected "int" [arg-type]
app/utils.py:5: note: Revealed type is "builtins.int"
"""
        result = self._make_parser().parse(content)
        assert result.errors == 2
        assert len(result.issues) == 3
        assert result.issues[0].rule_id == "name-defined"
        assert result.issues[0].line_number == 10

    def test_parse_empty(self) -> None:
        result = self._make_parser().parse("")
        assert result.total == 0
        assert not result.has_issues


class TestRuffParser:
    def _make_parser(self):
        return registry.get("ruff")

    def test_parse_text(self) -> None:
        content = """\
app/main.py:10:1: F401 `os` imported but unused
app/main.py:15:1: E501 line too long (120 > 88 characters)
"""
        result = self._make_parser().parse(content)
        assert result.errors == 2
        assert result.issues[0].rule_id == "F401"
        assert result.issues[1].rule_id == "E501"

    def test_parse_json(self) -> None:
        content = """[
  {
    "code": "F401",
    "filename": "app/main.py",
    "location": {"row": 10, "column": 1},
    "message": "`os` imported but unused"
  }
]"""
        result = self._make_parser().parse(content)
        assert result.errors == 1
        assert result.issues[0].rule_id == "F401"


class TestBanditParser:
    def _make_parser(self):
        return registry.get("bandit")

    def test_parse_issues(self) -> None:
        content = """{
  "results": [{
    "issue_severity": "HIGH",
    "issue_confidence": "HIGH",
    "test_id": "B101",
    "test_name": "assert_used",
    "issue_text": "Use of assert detected",
    "line_number": 10,
    "filename": "app/main.py"
  }],
  "metrics": {"total": 1, "SEVERITY.HIGH": 1, "SEVERITY.MEDIUM": 0, "SEVERITY.LOW": 0}
}"""
        result = self._make_parser().parse(content)
        assert result.high == 1
        assert len(result.issues) == 1
        assert result.issues[0].severity == Severity.HIGH


class TestCodeSnippet:
    def test_render(self) -> None:
        from ci_tool.parsers.models import CodeSnippet
        snippet = CodeSnippet(
            file_path="app/main.py",
            line_number=3,
            source="def foo():\n    x = 1\n    return x\n",
            context_lines=2,
        )
        rendered = snippet.render()
        assert "```python" in rendered
        assert "  3 | >" in rendered  # Error line marker
