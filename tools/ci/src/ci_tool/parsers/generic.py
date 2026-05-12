"""Generic fallback parser for unrecognized file types."""

from __future__ import annotations

import json

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
