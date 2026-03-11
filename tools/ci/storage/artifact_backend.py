"""Filesystem-based storage backend intended for use with GitHub artifacts.

The `ArtifactBackend` implements the `StorageBackend` interface by writing
JSON files into a directory structure that is convenient to upload as a
single artifact from GitHub Actions. Other workflows can then download and
re-use this directory to aggregate results across jobs.
"""
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List
from core.storage import StorageBackend


class ArtifactBackend(StorageBackend):
    """Storage backend that persists JSON files under a configurable prefix.

    Directory layout:

    - ``<prefix>/results`` – per-workflow results and reports
    - ``<prefix>/state`` – arbitrary workflow or run-level state
    """

    def __init__(self, config: Dict):
        """Initialize the backend and ensure directory structure exists.

        Args:
            config: Full configuration dictionary; the ``artifact.prefix``
                key controls the base directory used for storage.
        """
        self.config = config
        self.base_dir = Path(config.get('artifact', {}).get('prefix', 'ci-data'))
        self.results_dir = self.base_dir / 'results'
        self.state_dir = self.base_dir / 'state'

        # Create directories
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def save_workflow_result(self, result: Dict[str, Any]) -> None:
        """Persist a workflow result into the ``results`` directory.

        The result is written as ``<workflow>.json``, where ``workflow`` is
        taken from the ``workflow`` field in the result mapping and
        defaults to ``\"unknown\"`` if missing.
        """
        workflow = result.get('workflow', 'unknown')
        filename = self.results_dir / f"{workflow}.json"

        with open(filename, 'w') as f:
            json.dump(result, f, indent=2)

    def get_commit_results(self, commit: str) -> List[Dict[str, Any]]:
        """Return all stored workflow results associated with a commit SHA."""
        results = []
        for file in self.results_dir.glob('*.json'):
            with open(file, 'r') as f:
                data = json.load(f)
                if data.get('commit') == commit:
                    results.append(data)
        return results

    def save_state(self, key: str, data: Dict[str, Any]) -> None:
        """Serialize and store arbitrary state under ``state/<key>.json``."""
        filename = self.state_dir / f"{key}.json"
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

    def get_state(self, key: str) -> Dict[str, Any]:
        """Load a state mapping previously stored under ``state/<key>.json``.

        Returns an empty dictionary if no state file exists for the key.
        """
        filename = self.state_dir / f"{key}.json"
        if filename.exists():
            with open(filename, 'r') as f:
                return json.load(f)
        return {}

    def list_results(self, commit: str) -> List[str]:
        """List the workflow identifiers for results associated with a commit.

        The identifiers correspond to the stem (filename without extension)
        of JSON files in the ``results`` directory.
        """
        results = []
        for file in self.results_dir.glob('*.json'):
            with open(file, 'r') as f:
                data = json.load(f)
                if data.get('commit') == commit:
                    results.append(file.stem)
        return results

    def store_report(self, workflow_name: str, report: Dict[str, Any]) -> None:
        """Persist an aggregated workflow report in the ``results`` directory."""
        filename = self.results_dir / f"{workflow_name}_report.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)

    def load_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Load and return all JSON state files from the ``state`` directory."""
        states = {}
        for file in self.state_dir.glob('*.json'):
            with open(file, 'r') as f:
                states[file.stem] = json.load(f)
        return states
