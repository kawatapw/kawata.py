"""Test configuration for CI tool."""

from __future__ import annotations

import sys
from pathlib import Path

# Add tools/ci to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tools" / "ci"))
