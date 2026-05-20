#!/usr/bin/env python3
"""Quick test of mypy parser against actual mypy.log"""

from __future__ import annotations

import sys

sys.path.insert(0, "tools/ci/src")

from ci_tool.parsers.mypy import MypyParser

# Read the actual mypy.log
with open("reports/mypy.log") as f:
    content = f.read()

parser = MypyParser()
result = parser.parse(content, "reports/mypy.log")

print(f"Parser: {result.parser_name}")
print(f"Total issues: {result.total}")
print(f"Errors: {result.errors}")
print(f"Warnings: {result.warnings}")
print(f"Notes: {result.passed}")
print("\nFirst 10 issues:")
for i, issue in enumerate(result.issues[:10], 1):
    print(f"\n{i}. {issue.file_path}:{issue.line_number}:{issue.column}")
    print(f"   Severity: {issue.severity}")
    print(f"   Message: {issue.message}")
    if issue.rule_name:
        print(f"   Context: {issue.rule_name}")

if result.parse_error:
    print(f"\nParse error: {result.parse_error}")
else:
    print(f"\n✅ Successfully parsed {result.total} issues")
