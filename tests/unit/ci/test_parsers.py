"""Unit tests for CI tool parsers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add tools/ci to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tools" / "ci"))

from modules.parsers.bandit_parser import BanditParser
from modules.parsers.mypy_parser import MypyParser
from modules.parsers.pytest_parser import PytestParser
from modules.parsers.registry import detect_parser
from modules.parsers.registry import get_parser
from modules.parsers.registry import list_parsers
from modules.parsers.ruff_parser import RuffParser
from modules.parsers.safety_parser import SafetyParser
from modules.parsers.trivy_parser import TrivyParser
from modules.parsers.ty_parser import TyParser


class TestParserRegistry:
    """Test parser registry functionality."""

    def test_list_parsers(self):
        """Test that all parsers are registered."""
        parsers = list_parsers()
        assert "mypy" in parsers
        assert "ruff" in parsers
        assert "trivy" in parsers
        assert "safety" in parsers
        assert "bandit" in parsers
        assert "pytest" in parsers
        assert "generic" in parsers

    def test_get_parser(self):
        """Test getting parser instances."""
        mypy_parser = get_parser("mypy")
        assert isinstance(mypy_parser, MypyParser)

        ruff_parser = get_parser("ruff")
        assert isinstance(ruff_parser, RuffParser)

    def test_get_unknown_parser(self):
        """Test getting unknown parser raises error."""
        with pytest.raises(ValueError, match="Unknown parser"):
            get_parser("unknown")


class TestMypyParser:
    """Test mypy parser."""

    def test_parse_errors(self):
        """Test parsing mypy errors."""
        content = """
app/main.py:10: error: Name "x" is not defined [name-defined]
app/main.py:15: error: Argument 1 to "func" has incompatible type "str"; expected "int" [arg-type]
app/utils.py:5: note: Revealed type is "builtins.int"
"""
        parser = MypyParser()
        result = parser.parse(content)

        assert result["type"] == "mypy"
        assert result["summary"]["total_errors"] == 2
        assert result["summary"]["total_notes"] == 1
        assert (
            result["summary"]["files_with_errors"] == 1
        )  # Only app/main.py has errors
        assert len(result["issues"]) == 3

        # Check first issue
        issue = result["issues"][0]
        assert issue["file"] == "app/main.py"
        assert issue["line"] == 10
        assert issue["severity"] == "error"
        assert issue["error_code"] == "name-defined"

    def test_parse_empty(self):
        """Test parsing empty content."""
        parser = MypyParser()
        result = parser.parse("")

        assert result["type"] == "mypy"
        assert result["summary"]["total_errors"] == 0
        assert len(result["issues"]) == 0


class TestRuffParser:
    """Test ruff parser."""

    def test_parse_text_format(self):
        """Test parsing ruff text output."""
        content = """
app/main.py:10:1: F401 `os` imported but unused
app/main.py:15:1: E501 line too long (120 > 88 characters)
"""
        parser = RuffParser()
        result = parser.parse(content)

        assert result["type"] == "ruff"
        assert result["summary"]["total_violations"] == 2
        assert "F401" in result["summary"]["rules"]
        assert "E501" in result["summary"]["rules"]
        assert len(result["violations"]) == 2

    def test_parse_json_format(self):
        """Test parsing ruff JSON output."""
        content = """[
  {
    "code": "F401",
    "filename": "app/main.py",
    "location": {"row": 10, "column": 1},
    "end_location": {"row": 10, "column": 5},
    "message": "`os` imported but unused",
    "fix": null
  }
]"""
        parser = RuffParser()
        result = parser.parse(content)

        assert result["type"] == "ruff"
        assert result["summary"]["total_violations"] == 1
        assert result["violations"][0]["rule_code"] == "F401"
        assert result["violations"][0]["fixable"] is False


class TestTrivyParser:
    """Test trivy parser."""

    def test_parse_sarif_format(self):
        """Test parsing trivy SARIF output."""
        content = """{
  "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "results": [
        {
          "ruleId": "CVE-2023-1234",
          "level": "error",
          "message": {"text": "Critical vulnerability"},
          "locations": []
        }
      ]
    }
  ]
}"""
        parser = TrivyParser()
        result = parser.parse(content)

        assert result["type"] == "trivy"
        assert result["summary"]["total_vulnerabilities"] == 1
        assert result["summary"]["critical"] == 1

    def test_parse_json_format(self):
        """Test parsing trivy JSON output."""
        content = """{
  "Results": [
    {
      "Target": "requirements.txt",
      "Vulnerabilities": [
        {
          "VulnerabilityID": "CVE-2023-1234",
          "Severity": "HIGH",
          "PkgName": "requests",
          "InstalledVersion": "2.28.0",
          "FixedVersion": "2.28.1",
          "Title": "Security vulnerability"
        }
      ]
    }
  ]
}"""
        parser = TrivyParser()
        result = parser.parse(content)

        assert result["type"] == "trivy"
        assert result["summary"]["total_vulnerabilities"] == 1
        assert result["summary"]["high"] == 1
        assert result["vulnerabilities"][0]["package"] == "requests"


class TestSafetyParser:
    """Test safety parser."""

    def test_parse_vulnerabilities(self):
        """Test parsing safety vulnerabilities."""
        content = """{
  "vulnerabilities": [
    {
      "id": "12345",
      "package": "requests",
      "installed_version": "2.28.0",
      "affected_versions": "<2.28.1",
      "severity": "high",
      "advisory": "Security vulnerability in requests"
    }
  ],
  "scanned_packages": {
    "requests": "2.28.0",
    "flask": "2.0.0"
  }
}"""
        parser = SafetyParser()
        result = parser.parse(content)

        assert result["type"] == "safety"
        assert result["summary"]["total_vulnerabilities"] == 1
        assert result["summary"]["packages_scanned"] == 2
        assert result["vulnerabilities"][0]["package"] == "requests"


class TestDetectParser:
    """Test parser auto-detection."""

    def test_detect_by_filename(self):
        """Test detection by filename patterns."""
        assert detect_parser("mypy-output.txt") == "mypy"
        assert detect_parser("ruff-results.json") == "ruff"
        assert detect_parser("trivy-results.sarif") == "trivy"
        assert detect_parser("safety-report.json") == "safety"
        assert detect_parser("bandit-output.json") == "bandit"
        assert detect_parser("junit.xml") == "pytest"

    def test_detect_by_extension(self):
        """Test detection by file extension."""
        assert detect_parser("report.xml") == "pytest"
        assert detect_parser("report.sarif") == "trivy"

    def test_detect_json_by_content(self):
        """Test JSON detection by content."""
        # SARIF content
        sarif_content = '{"$schema": "https://sarif-schema"}'
        assert detect_parser("report.json", sarif_content) == "trivy"

        # Safety content
        safety_content = '{"vulnerabilities": [], "scanned_packages": {}}'
        assert detect_parser("report.json", safety_content) == "safety"

        # Bandit content
        bandit_content = '{"results": [], "metrics": {}}'
        assert detect_parser("report.json", bandit_content) == "bandit"

    def test_detect_text_by_content(self):
        """Test text detection by content."""
        # Mypy content
        mypy_content = 'app/main.py:10: error: Name "x" is not defined'
        assert detect_parser("output.txt", mypy_content) == "mypy"

        # Ruff content
        ruff_content = "app/main.py:10:1: F401 `os` imported but unused"
        assert detect_parser("output.txt", ruff_content) == "ruff"


class TestBanditParser:
    """Test bandit parser (existing)."""

    def test_parse_issues(self):
        """Test parsing bandit issues."""
        content = """{
  "results": [
    {
      "issue_severity": "HIGH",
      "issue_confidence": "HIGH",
      "test_id": "B101",
      "test_name": "assert_used",
      "issue_text": "Use of assert detected",
      "line_number": 10,
      "filename": "app/main.py"
    }
  ],
  "metrics": {
    "total": 1,
    "SEVERITY.HIGH": 1,
    "SEVERITY.MEDIUM": 0,
    "SEVERITY.LOW": 0
  }
}"""
        parser = BanditParser()
        result = parser.parse(content)

        assert result["type"] == "bandit"
        assert result["summary"]["total_issues"] == 1
        assert result["summary"]["high_severity"] == 1
        assert len(result["issues"]) == 1


class TestPytestParser:
    """Test pytest parser (existing)."""

    def test_parse_junit_xml(self):
        """Test parsing pytest junit XML."""
        content = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="10" errors="0" failures="1" skipped="2" time="5.5">
    <testcase classname="test_module" name="test_pass" time="0.1"/>
    <testcase classname="test_module" name="test_fail" time="0.2">
      <failure message="AssertionError">assert False</failure>
    </testcase>
    <testcase classname="test_module" name="test_skip" time="0.0">
      <skipped type="pytest.skip" message="Skipped"/>
    </testcase>
  </testsuite>
</testsuites>"""
        parser = PytestParser()
        result = parser.parse(content)

        assert result["type"] == "pytest"
        assert result["summary"]["total"] == 10
        assert result["summary"]["failed"] == 1
        assert result["summary"]["skipped"] == 2
        assert len(result["test_cases"]) == 3


class TestTyParser:
    """Test ty parser."""

    def test_parse_junit_xml(self):
        """Test parsing ty JUnit XML output."""
        content = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="ty" tests="3" errors="0" failures="1" skipped="0" time="1.5">
    <testcase classname="ty" name="Type check: app/main.py" file="app/main.py" line="10" time="0.5"/>
    <testcase classname="ty" name="Type check: app/utils.py" file="app/utils.py" line="20" time="0.3">
      <failure message="Type error: Incompatible types in assignment">Expected 'int', got 'str'</failure>
    </testcase>
    <testcase classname="ty" name="Type check: app/models.py" file="app/models.py" line="15" time="0.7"/>
  </testsuite>
</testsuites>"""
        parser = TyParser()
        result = parser.parse(content)

        assert result["type"] == "ty"
        assert result["summary"]["total"] == 3
        assert result["summary"]["failed"] == 1
        assert result["summary"]["passed"] == 2
        assert len(result["test_cases"]) == 3

        # Check the failed test case
        failed_case = [tc for tc in result["test_cases"] if tc["status"] == "failed"][0]
        assert failed_case["file"] == "app/utils.py"
        assert failed_case["line"] == 20
        assert "Type error" in failed_case["message"]

    def test_parse_empty(self):
        """Test parsing empty content."""
        parser = TyParser()
        result = parser.parse("")

        assert result["type"] == "ty"
        assert result["summary"]["total"] == 0
        assert len(result["test_cases"]) == 0
