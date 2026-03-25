# Module registry for CI tool
import importlib
import sys
from pathlib import Path
from typing import Any

# Add tools/ci to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_module(module_name: str) -> Any:
    """Load a module by name."""
    try:
        # Try to import the module directly
        module = importlib.import_module(f"modules.{module_name}")

        # If the module is a package (has __path__), try to import the main module file
        if hasattr(module, "__path__"):
            try:
                main_module = importlib.import_module(
                    f"modules.{module_name}.{module_name}",
                )
                return main_module
            except ImportError as inner_e:
                # Re-raise with more context
                raise ImportError(
                    f"Failed to import modules.{module_name}.{module_name}: {inner_e}",
                ) from inner_e

        return module
    except ImportError as e:
        raise ValueError(f"Unknown module: {module_name}: {e}") from e
