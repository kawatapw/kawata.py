"""Pytest result parser."""
import xml.etree.ElementTree as ET
from typing import Dict, Any
from .registry import Parser, register_parser


class PytestParser(Parser):
    """Parser for pytest XML results."""

    def parse(self, content: str) -> Dict[str, Any]:
        """Parse pytest XML content."""
        root = ET.fromstring(content)

        # Extract test summary
        summary = {
            'total': int(root.get('tests', 0)),
            'passed': int(root.get('passed', 0)),
            'failed': int(root.get('failed', 0)),
            'skipped': int(root.get('skipped', 0)),
            'errors': int(root.get('errors', 0)),
            'duration': float(root.get('time', 0))
        }

        # Extract test cases
        test_cases = []
        for testcase in root.findall('.//testcase'):
            test_case = {
                'name': testcase.get('name'),
                'classname': testcase.get('classname'),
                'file': testcase.get('file'),
                'line': int(testcase.get('line', 0)),
                'duration': float(testcase.get('time', 0))
            }

            # Check for failures
            failure = testcase.find('failure')
            if failure is not None:
                test_case['status'] = 'failed'
                test_case['message'] = failure.get('message', '')
                test_case['type'] = failure.get('type', '')
            else:
                test_case['status'] = 'passed'

            test_cases.append(test_case)

        return {
            'type': 'pytest',
            'summary': summary,
            'test_cases': test_cases
        }

    def get_type(self) -> str:
        """Get parser type name."""
        return 'pytest'


# Register the parser
register_parser('pytest', PytestParser)
