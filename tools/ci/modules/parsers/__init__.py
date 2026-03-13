# Parsers module
# Auto-import all parsers to trigger registration

from . import bandit_parser  # noqa: F401
from . import generic_parser  # noqa: F401
from . import pytest_parser  # noqa: F401
from . import mypy_parser  # noqa: F401
from . import ruff_parser  # noqa: F401
from . import trivy_parser  # noqa: F401
from . import safety_parser  # noqa: F401

# Re-export registry functions for convenience
from .registry import (  # noqa: F401
    Parser,
    register_parser,
    get_parser,
    list_parsers,
    detect_parser,
    parse_file,
)
