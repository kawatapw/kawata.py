"""Parser registry for CI tool."""
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod


class Parser(ABC):
    """Abstract parser interface."""

    @abstractmethod
    def parse(self, content: str) -> Dict[str, Any]:
        """Parse content and return structured data."""
        pass

    @abstractmethod
    def get_type(self) -> str:
        """Get parser type name."""
        pass


# Parser registry
_PARSERS: Dict[str, type] = {}


def register_parser(name: str, parser_class: type) -> None:
    """Register a parser."""
    _PARSERS[name] = parser_class


def get_parser(name: str) -> Parser:
    """Get a parser instance."""
    if name not in _PARSERS:
        raise ValueError(f"Unknown parser: {name}. Available parsers: {list(_PARSERS.keys())}")
    return _PARSERS[name]()


def list_parsers() -> list:
    """List all registered parser names."""
    return list(_PARSERS.keys())


def detect_parser(file_path: str, content: Optional[str] = None) -> str:
    """Auto-detect the appropriate parser for a file.

    Detection strategy:
    1. Filename-based detection (e.g., *mypy*, *ruff*, *trivy*, *safety*)
    2. File extension detection (.xml, .json, .sarif, .txt, .log)
    3. Content-based detection for JSON files

    Args:
        file_path: Path to the file
        content: Optional file content for content-based detection

    Returns:
        Parser name string
    """
    path = Path(file_path)
    filename = path.name.lower()
    stem = path.stem.lower()
    suffix = path.suffix.lower()

    # 1. Filename-based detection
    filename_patterns = {
        'mypy': ['mypy'],
        'ruff': ['ruff'],
        'trivy': ['trivy'],
        'safety': ['safety'],
        'bandit': ['bandit'],
        'pytest': ['junit', 'pytest', 'test-results'],
    }

    for parser_name, patterns in filename_patterns.items():
        for pattern in patterns:
            if pattern in filename or pattern in stem:
                return parser_name

    # 2. File extension detection
    if suffix == '.xml':
        return 'pytest'
    elif suffix == '.sarif':
        return 'trivy'
    elif suffix in ('.txt', '.log'):
        # Try to detect by content if available
        if content:
            return _detect_text_format(content)
        return 'generic'
    elif suffix == '.json':
        # 3. Content-based detection for JSON
        if content:
            return _detect_json_format(content)
        # Try to read file for detection
        try:
            with open(file_path, 'r') as f:
                file_content = f.read()
                return _detect_json_format(file_content)
        except Exception:
            return 'generic'
    else:
        return 'generic'


def _detect_json_format(content: str) -> str:
    """Detect JSON format by examining content structure."""
    try:
        data = json.loads(content)

        # Check for SARIF format (Trivy)
        if isinstance(data, dict):
            schema = data.get('$schema', '')
            if 'sarif' in schema.lower():
                return 'trivy'

            # Check for Trivy JSON format
            if 'Results' in data or 'results' in data:
                results = data.get('Results', data.get('results', []))
                if isinstance(results, list) and len(results) > 0:
                    first = results[0]
                    if isinstance(first, dict) and ('Vulnerabilities' in first or 'Target' in first):
                        return 'trivy'

            # Check for Safety format
            if 'vulnerabilities' in data or 'scanned_packages' in data:
                return 'safety'

            # Check for Bandit format
            if 'results' in data or 'metrics' in data:
                if isinstance(data.get('results'), list) or isinstance(data.get('metrics'), dict):
                    return 'bandit'

        # Check for Ruff JSON format (array of violations)
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            if isinstance(first, dict) and ('code' in first or 'rule_code' in first):
                return 'ruff'

        return 'generic'
    except json.JSONDecodeError:
        return 'generic'


def _detect_text_format(content: str) -> str:
    """Detect text format by examining content patterns."""
    lines = content.strip().split('\n')
    if not lines:
        return 'generic'

    first_line = lines[0]

    # Check for mypy pattern: file:line: severity: message
    mypy_pattern = re.compile(r'^[^:]+:\d+:\s*(error|note|warning):')
    if mypy_pattern.match(first_line):
        return 'mypy'

    # Check for ruff pattern: file:line:col: RULE_CODE message
    ruff_pattern = re.compile(r'^[^:]+:\d+:\d+:\s*[A-Z]+\d+')
    if ruff_pattern.match(first_line):
        return 'ruff'

    return 'generic'


def parse_file(file_path: str, parser_name: Optional[str] = None) -> Dict[str, Any]:
    """Parse a file using the appropriate parser.

    Args:
        file_path: Path to the file to parse
        parser_name: Optional explicit parser name. If None, auto-detects.

    Returns:
        Parsed data dictionary
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Auto-detect parser if not specified
    if parser_name is None:
        parser_name = detect_parser(file_path, content)

    parser = get_parser(parser_name)
    return parser.parse(content)


# Import and register all parsers
# This ensures all parsers are available when the registry is imported
try:
    from . import bandit_parser  # noqa: F401
except ImportError:
    pass

try:
    from . import generic_parser  # noqa: F401
except ImportError:
    pass

try:
    from . import pytest_parser  # noqa: F401
except ImportError:
    pass

try:
    from . import mypy_parser  # noqa: F401
except ImportError:
    pass

try:
    from . import ruff_parser  # noqa: F401
except ImportError:
    pass

try:
    from . import trivy_parser  # noqa: F401
except ImportError:
    pass

try:
    from . import safety_parser  # noqa: F401
except ImportError:
    pass
