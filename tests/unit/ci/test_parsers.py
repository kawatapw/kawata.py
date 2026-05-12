"""Tests for all parsers."""

from __future__ import annotations

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

    def test_parse_error_element(self) -> None:
        """Test that <error> elements are parsed (not just <failure>)."""
        content = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="1" errors="1" failures="0" skipped="0" time="1.0">
    <testcase classname="test_module" name="test_error" time="0.1">
      <error message="collection failure">ImportError: No module named 'core'</error>
    </testcase>
  </testsuite>
</testsuites>"""
        result = self._make_parser().parse(content)
        assert result.total == 1
        assert result.errors == 1
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
app/main.py:10:5:10:15: error: Name "x" is not defined [name-defined]
app/main.py:15:5:15:20: error: Argument 1 has incompatible type "str"; expected "int" [arg-type]
app/utils.py:5:5:5:10: note: Revealed type is "builtins.int"
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
  "metrics": {
    "_totals": {"SEVERITY.HIGH": 1, "SEVERITY.MEDIUM": 0, "SEVERITY.LOW": 0}
  }
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
        assert "  3 |     return x" in rendered  # Error line
        assert "     | " in rendered  # Caret line
