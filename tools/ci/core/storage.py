"""Storage backend abstractions and registry for the CI tool.

This module defines the abstract `StorageBackend` interface, which concrete
backends (such as the artifact-backed implementation) must implement, and a
simple registry that allows the rest of the system to look up backends by
name from configuration.
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Any


class StorageBackend(ABC):
    """Abstract storage backend interface.

    Concrete implementations are responsible for persisting workflow state,
    results, and reports in a way that can later be retrieved for summary
    and aggregation.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the storage backend with configuration.

        Args:
            config: Configuration dictionary for the backend.
        """
        self.config = config

    @abstractmethod
    def save_workflow_result(self, result: dict[str, Any]) -> None:
        """Persist a single workflow result entry.

        Args:
            result: Mapping containing at minimum identifying information
                about the workflow (e.g. name, run ID, commit) and any
                additional fields needed by the backend.
        """
        pass

    @abstractmethod
    def get_commit_results(self, commit: str) -> list[dict[str, Any]]:
        """Return all workflow results associated with a given commit.

        Args:
            commit: Commit SHA to filter results by.

        Returns:
            A list of result dictionaries previously stored via
            `save_workflow_result`.
        """
        pass

    @abstractmethod
    def save_state(self, key: str, data: dict[str, Any]) -> None:
        """Persist arbitrary workflow or run-level state.

        Args:
            key: Logical identifier for the piece of state (for example a
                workflow name or composite key).
            data: JSON-serializable mapping to store.
        """
        pass

    @abstractmethod
    def get_state(self, key: str) -> dict[str, Any]:
        """Load arbitrary state previously saved under a key.

        Args:
            key: Identifier used when calling `save_state`.

        Returns:
            The stored mapping, or an empty dict if no state exists for
            the given key (exact semantics are backend-dependent).
        """
        pass

    @abstractmethod
    def list_results(self, commit: str) -> list[str]:
        """List identifiers for all results associated with a commit.

        This is typically used by aggregation code to find all stored
        results before loading them.

        Args:
            commit: Commit SHA to enumerate results for.

        Returns:
            A list of backend-specific identifiers for results.
        """
        pass

    @abstractmethod
    def store_report(self, workflow_name: str, report: dict[str, Any]) -> None:
        """Persist a fully-aggregated report for a single workflow.

        Args:
            workflow_name: Logical name of the workflow this report covers.
            report: JSON-serializable mapping containing the report body.
        """
        pass

    @abstractmethod
    def load_all_states(self) -> dict[str, dict[str, Any]]:
        """Load all stored workflow state entries.

        Returns:
            A mapping from state keys to their stored payloads. The
            concrete backend decides what constitutes a "state key".
        """
        pass


# Backend registry
_BACKENDS = {}


def register_backend(name: str, backend_class: type[StorageBackend]) -> None:
    """Register a concrete storage backend class.

    This is typically called from backend modules at import time.

    Args:
        name: Symbolic backend name used in configuration (for example
            ``\"artifact\"``).
        backend_class: Class implementing the `StorageBackend` interface.
    """
    _BACKENDS[name] = backend_class


def get_backend(name: str, config: dict[str, Any]) -> StorageBackend:
    """Instantiate a registered storage backend.

    Args:
        name: Backend name previously passed to `register_backend`.
        config: Full configuration dictionary for the current run.

    Returns:
        An initialized `StorageBackend` instance.

    Raises:
        ValueError: If no backend has been registered under ``name``.
    """
    if name not in _BACKENDS:
        raise ValueError(f"Unknown storage backend: {name}")
    return _BACKENDS[name](config)


# Register artifact backend (lazy import to avoid circular dependency)
def _register_artifact_backend() -> None:
    from storage.artifact_backend import ArtifactBackend

    register_backend("artifact", ArtifactBackend)


_register_artifact_backend()
