# Parsers module
# Auto-import all parsers to trigger registration
from __future__ import annotations

from . import bandit_parser
from . import generic_parser
from . import mypy_parser
from . import pytest_parser
from . import ruff_parser
from . import safety_parser
from . import trivy_parser

# Re-export registry functions for convenience
from .registry import Parser
from .registry import detect_parser
from .registry import get_parser
from .registry import list_parsers
from .registry import parse_file
from .registry import register_parser
