"""Parser registry for CI tool."""
import json
from typing import Dict, Any, List, Optional
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
_PARSERS = {}


def register_parser(name: str, parser_class):
    """Register a parser."""
    _PARSERS[name] = parser_class


def get_parser(name: str) -> Parser:
    """Get a parser instance."""
    if name not in _PARSERS:
        raise ValueError(f"Unknown parser: {name}")
    return _PARSERS[name]()


def parse_file(file_path: str, parser_name: Optional[str] = None) -> Dict[str, Any]:
    """Parse a file using the appropriate parser."""
    from pathlib import Path

    path = Path(file_path)

    # Auto-detect parser based on file extension
    if parser_name is None:
        if path.suffix == '.xml':
            parser_name = 'pytest'
        elif path.suffix == '.json':
            # Check if it's bandit format
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    if 'results' in data or 'issues' in data:
                        parser_name = 'bandit'
                    else:
                        parser_name = 'generic'
            except Exception:
                parser_name = 'generic'
        else:
            parser_name = 'generic'

    parser = get_parser(parser_name)

    with open(file_path, 'r') as f:
        content = f.read()

    return parser.parse(content)
