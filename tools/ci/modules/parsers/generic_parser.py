"""Generic parser for unknown file types."""
import json
from typing import Dict, Any
from .registry import Parser, register_parser


class GenericParser(Parser):
    """Parser for generic/unrecognized file types."""

    def parse(self, content: str) -> Dict[str, Any]:
        """Parse generic content."""
        # Try to parse as JSON first
        try:
            data = json.loads(content)
            return {
                'type': 'generic_json',
                'data': data
            }
        except json.JSONDecodeError:
            # Return as raw text
            return {
                'type': 'generic_text',
                'content': content,
                'lines': len(content.split('\n'))
            }

    def get_type(self) -> str:
        """Get parser type name."""
        return 'generic'


# Register the parser
register_parser('generic', GenericParser)
