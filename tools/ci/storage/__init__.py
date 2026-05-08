"""Storage backend implementations for the CI tool.

The `core.storage` module defines the `StorageBackend` interface and the
backend registry; this package contains concrete backend implementations
that can be selected via configuration.
"""

from __future__ import annotations

from .artifact_backend import ArtifactBackend
