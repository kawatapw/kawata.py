"""Error types and centralised error handling for the CI tool.

This module defines a small hierarchy of exception classes used throughout
the project as well as a helper for consistently surfacing errors to users
and, when available, to the GitHub Actions job summary.
"""
import sys
import traceback
from typing import Dict, Any
from .context import Context


class CIError(Exception):
    """Base class for all CI tool errors.

    Subclasses should provide a more specific ``error_type`` so that
    downstream consumers (for example summary renderers) can distinguish
    between configuration problems, storage issues, and module failures.
    """
    def __init__(self, message: str, error_type: str = "ci_error"):
        self.message = message
        self.error_type = error_type
        super().__init__(message)


class ConfigError(CIError):
    """Raised when configuration is invalid or inconsistent."""
    def __init__(self, message: str):
        super().__init__(message, "config_error")


class StorageError(CIError):
    """Raised when a storage backend cannot fulfill an operation."""
    def __init__(self, message: str):
        super().__init__(message, "storage_error")


class ModuleError(CIError):
    """Raised when an individual CI module fails during execution."""
    def __init__(self, message: str):
        super().__init__(message, "module_error")


def handle_error(error: Exception, context: Context, config: Dict[str, Any]) -> None:
    """Render an error in a user-visible way and optionally annotate CI output.

    This helper prints a concise error message to stderr and, when debug
    mode is enabled, includes a full traceback. If the tool is running
    inside GitHub Actions and the `GITHUB_STEP_SUMMARY` file is available,
    it also appends a short error section to the job summary so failures
    are visible directly in the Actions UI.

    Args:
        error: The exception instance that was raised.
        context: Execution context describing the current workflow and run.
        config: Resolved configuration dictionary; only the ``debug`` flag
            is currently consulted.
    """
    error_info = {
        'type': type(error).__name__,
        'message': str(error),
        'traceback': traceback.format_exc() if config.get('debug') else None,
        'context': {
            'workflow': context.workflow_name,
            'run_id': context.run_id,
            'commit': context.commit_sha
        }
    }

    # Log to stderr
    print(f"ERROR: {error}", file=sys.stderr)

    if config.get('debug'):
        print(error_info['traceback'], file=sys.stderr)

    # Write to job summary if in GitHub Actions
    if context.is_github_actions and context.step_summary_path:
        from pathlib import Path
        summary_path = Path(context.step_summary_path)
        with open(summary_path, 'a') as f:
            f.write(f"\n### Error\n**Type:** {error_info['type']}\n**Message:** {error_info['message']}\n")
