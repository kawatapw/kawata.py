# Parsers module
# Auto-import all parsers to trigger registration

from . import (
    bandit_parser,  # noqa: F401
    generic_parser,  # noqa: F401
    mypy_parser,  # noqa: F401
    pytest_parser,  # noqa: F401
    ruff_parser,  # noqa: F401
    safety_parser,  # noqa: F401
    trivy_parser,  # noqa: F401
)

# Re-export registry functions for convenience
from .registry import (  # noqa: F401
    Parser,
    detect_parser,
    get_parser,
    list_parsers,
    parse_file,
    register_parser,
)
