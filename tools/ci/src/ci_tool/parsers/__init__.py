"""Parser plugin system."""

from __future__ import annotations

import importlib
import pkgutil
from abc import ABC, abstractmethod
from pathlib import Path

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
        self, file_path: str, error_line: int, context: int = 2
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
            raise KeyError(f"Unknown parser: '{name}'. Available: {available}")
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

            # Bandit (check before trivy — bandit has both "results" and "metrics")
            if "results" in data and "metrics" in data:
                return self._parsers.get("bandit", self._parsers["generic"])

            # Trivy JSON
            if "Results" in data or "results" in data:
                return self._parsers.get("trivy", self._parsers["generic"])

            # Safety
            if "vulnerabilities" in data or "scanned_packages" in data:
                return self._parsers.get("safety", self._parsers["generic"])

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
        package_dir = Path(__file__).parent
        for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
            if module_name in ("models",):
                continue
            importlib.import_module(f"ci_tool.parsers.{module_name}")


# Global registry instance
registry = ParserRegistry()
