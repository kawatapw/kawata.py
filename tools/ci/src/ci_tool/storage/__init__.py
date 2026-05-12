"""Storage backend abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ci_tool.storage.models import WorkflowState


class StorageBackend(ABC):
    """Abstract storage for workflow state and results.

    Implementations must be thread-safe for parallel job execution.
    """

    @abstractmethod
    def save_state(self, state: WorkflowState) -> None:
        """Persist workflow state."""

    @abstractmethod
    def load_state(self, run_id: str) -> WorkflowState | None:
        """Load workflow state by run ID."""

    @abstractmethod
    def save_job_result(self, run_id: str, state: WorkflowState) -> None:
        """Save/update a single job result within workflow state."""

    @abstractmethod
    def list_runs(self, limit: int = 10) -> list[str]:
        """List recent run IDs, newest first."""

    @abstractmethod
    def cleanup(self, keep_last: int = 30) -> int:
        """Remove old runs. Returns count of removed entries."""
