"""Configuration loading and merging for the CI tool.

The configuration system is intentionally simple: it starts from a set of
reasonable defaults and then applies overrides from, in order of priority:

1. A YAML configuration file (by default `.ci/config.yaml`)
2. Environment variables
3. Command-line flags

The final configuration dictionary is passed around to other modules and
backends and is expected to be JSON-serializable.
"""

import argparse
import os
from pathlib import Path
from typing import Any

import yaml


def load_config(args: argparse.Namespace) -> dict[str, Any]:
    """Load and resolve configuration for a single CI invocation.

    The configuration precedence is:

    1. Built-in defaults
    2. YAML file pointed to by `args.config`, `CI_CONFIG_PATH`, or
       `.ci/config.yaml` (first that exists)
    3. Environment variables such as `CI_STORAGE`
    4. Explicit command-line flags on `args`

    Args:
        args: Parsed CLI arguments, typically from `core.cli.parse_args`.

    Returns:
        A nested configuration dictionary containing merged settings for
        storage, reporting, summaries, and any custom keys defined in the
        YAML file.
    """

    config = {
        "storage": "artifact",
        "artifact": {"prefix": "ci-data"},
        "report": {"generate_final_report": True},
        "summary": {"include_artifacts": True},
    }

    # Load from config.yaml
    config_path = args.config or os.getenv("CI_CONFIG_PATH") or ".ci/config.yaml"
    if Path(config_path).exists():
        with open(config_path) as f:
            yaml_config = yaml.safe_load(f)
            if yaml_config:
                config = deep_merge(config, yaml_config)

    # Override with environment variables
    storage_env = os.getenv("CI_STORAGE")
    if storage_env:
        config["storage"] = storage_env

    # Override with CLI arguments
    if args.storage:
        config["storage"] = args.storage

    return config


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge two dictionaries.

    Values from ``override`` take precedence over values from ``base``.
    If both dictionaries contain a value for the same key and both values
    are dictionaries, they are merged recursively; otherwise the value from
    ``override`` fully replaces the one from ``base``.

    Args:
        base: Original mapping providing default values.
        override: Mapping whose values should overwrite or extend ``base``.

    Returns:
        A new dictionary containing the merged result.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
