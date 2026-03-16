#!/usr/bin/env python3
"""Main entrypoint for the CI orchestration tool.

This module wires together argument parsing, configuration loading,
environment context construction, and dynamic dispatch into the
individual CI modules. It is intentionally thin so that most logic
remains testable in the underlying packages.
"""
import sys
import argparse
from pathlib import Path
from typing import Any

from core.cli import parse_args
from core.context import build_context
from core.config import load_config
from core.errors import handle_error
from modules import load_module


def print_json(result: Any) -> None:
    """Render a Python object as pretty-printed JSON on stdout.

    Args:
        result: Any JSON-serializable object to be emitted.
    """
    import json
    print(json.dumps(result, indent=2))


def print_result(result: Any) -> None:
    """Print a result object in a simple, human-readable form.

    Dictionary results are rendered as ``key: value`` lines; all other
    types are printed via ``str(result)``. This is intended for local
    usage or non-JSON CI logs.

    Args:
        result: Object produced by a module action.
    """
    if isinstance(result, dict):
        for key, value in result.items():
            print(f"{key}: {value}")
    else:
        print(result)


def main() -> None:
    """Entry point for the `ci` CLI.

    This function is responsible for:

    - Parsing command-line arguments
    - Loading configuration and environment context
    - Optionally launching an interactive TUI when no module is provided
    - Dispatching to the selected module action
    - Handling errors via `core.errors.handle_error`

    It is invoked when the module is executed as a script.
    """
    # Parse arguments
    args = parse_args()

    # Load configuration (CLI > env > config.yaml)
    config = load_config(args)

    # Build context from GitHub environment
    context = build_context()

    # Handle TUI mode if no args and interactive
    if not args.module and context.is_interactive:
        launch_tui()
        return

    # Load and execute module
    try:
        module = load_module(args.module)
        action = getattr(module, args.action)
        result = action(args, context, config)

        if args.json:
            print_json(result)
        else:
            print_result(result)

    except Exception as e:
        handle_error(e, context, config)
        sys.exit(1)


def launch_tui() -> None:
    """Launch the (placeholder) interactive TUI mode.

    Currently this is a stub that prints a short help message; it exists
    mainly so callers do not need to guard against its absence.
    """
    print("CI Tool - TUI Mode")
    print("Use --help for command line options")


if __name__ == "__main__":
    main()
