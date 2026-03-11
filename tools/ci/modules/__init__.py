# Module registry for CI tool
import importlib
import sys
from pathlib import Path

# Add tools/ci to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def load_module(module_name: str):
    """Load a module by name."""
    try:
        # Try to import the module directly
        module = importlib.import_module(f'modules.{module_name}')
        
        # If the module is a package (has __path__), try to import the main module file
        if hasattr(module, '__path__'):
            try:
                main_module = importlib.import_module(f'modules.{module_name}.{module_name}')
                return main_module
            except ImportError:
                pass
        
        return module
    except ImportError as e:
        raise ValueError(f"Unknown module: {module_name}") from e
