# CI TOOL IMPLEMENTATION GUIDE
## Notes for AI Implementation

This document contains implementation-specific details and patterns to follow when building the CI tool. Use this as a reference when switching to code mode.

---

## PROJECT STRUCTURE

```
tools/ci/
├── ci.py                          # Main CLI entrypoint
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── cli.py                     # CLI argument parsing
│   ├── context.py                 # GitHub environment context
│   ├── config.py                  # Configuration system
│   ├── storage.py                 # Storage interface
│   ├── errors.py                  # Error handling
│   └── logging.py                 # Logging setup
├── modules/
│   ├── __init__.py                # Module registry
│   ├── workflow/
│   │   ├── __init__.py
│   │   └── workflow.py            # workflow start/finish
│   ├── summary/
│   │   ├── __init__.py
│   │   └── summary.py             # GitHub job summaries
│   ├── report/
│   │   ├── __init__.py
│   │   └── report.py              # Report aggregation
│   ├── artifacts/
│   │   ├── __init__.py
│   │   └── artifacts.py           # Artifact management
│   └── parsers/
│       ├── __init__.py
│       ├── registry.py            # Parser registry
│       ├── pytest_parser.py
│       ├── bandit_parser.py
│       └── generic_parser.py
├── storage/
│   ├── __init__.py
│   ├── backend.py                 # Storage backend interface
│   └── artifact_backend.py        # GitHub artifact implementation
├── templates/
│   ├── workflow_summary.md
│   └── ci_report.md
├── utils/
│   ├── __init__.py
│   ├── github.py                  # GitHub API helpers
│   └── timing.py                  # Timing utilities
└── scripts/
    └── ci-bootstrap.sh            # Bootstrap timing script
```

---

## CORE IMPLEMENTATION PATTERNS

### 1. CLI Entry Point (`ci.py`)

**Key Responsibilities:**
- Parse command-line arguments using `argparse`
- Detect if running in interactive terminal
- Load configuration from multiple sources
- Initialize context object
- Route to appropriate module/action
- Handle errors centrally

**Implementation Pattern:**
```python
#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path

# Add tools/ci to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from core.cli import parse_args
from core.context import build_context
from core.config import load_config
from core.errors import handle_error
from modules import load_module


def main():
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


if __name__ == "__main__":
    main()
```

**Important:** Always use `sys.exit(1)` on errors to ensure CI workflows fail properly.

---

### 2. Argument Parsing (`core/cli.py`)

**Key Pattern:** Use subparsers for module/action structure

```python
import argparse


def parse_args():
    parser = argparse.ArgumentParser(prog="ci", description="CI orchestration tool")

    # Global flags
    parser.add_argument("--storage", help="Storage backend")
    parser.add_argument("--config", help="Config file path")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--json", action="store_true")

    # Subparsers for modules
    subparsers = parser.add_subparsers(dest="module", help="Module name")

    # Workflow module
    workflow_parser = subparsers.add_parser("workflow", help="Workflow lifecycle")
    workflow_subparsers = workflow_parser.add_subparsers(dest="action")
    workflow_subparsers.add_parser("start", help="Start workflow")
    workflow_subparsers.add_parser("finish", help="Finish workflow")

    # Summary module
    summary_parser = subparsers.add_parser("summary", help="Job summaries")
    summary_subparsers = summary_parser.add_subparsers(dest="action")
    summary_subparsers.add_parser("generate", help="Generate summary")

    # Report module
    report_parser = subparsers.add_parser("report", help="CI reports")
    report_subparsers = report_parser.add_subparsers(dest="action")
    report_subparsers.add_parser("aggregate", help="Aggregate reports")

    # Artifacts module
    artifacts_parser = subparsers.add_parser("artifacts", help="Artifact management")
    artifacts_subparsers = artifacts_parser.add_subparsers(dest="action")
    artifacts_subparsers.add_parser("collect", help="Collect artifacts")

    return parser.parse_args()
```

**Important:** Use `dest='module'` and `dest='action'` to capture the command structure.

---

### 3. Context Object (`core/context.py`)

**Key Pattern:** Build context from GitHub environment variables

```python
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Context:
    commit_sha: str
    workflow_name: str
    job_name: str
    run_id: str
    run_number: str
    repository: str
    actor: str
    run_url: str
    is_github_actions: bool
    is_interactive: bool
    step_summary_path: Optional[str]


def build_context() -> Context:
    """Build context from GitHub environment variables."""
    github_sha = os.getenv("GITHUB_SHA", "")
    github_workflow = os.getenv("GITHUB_WORKFLOW", "")
    github_job = os.getenv("GITHUB_JOB", "")
    github_run_id = os.getenv("GITHUB_RUN_ID", "")
    github_run_number = os.getenv("GITHUB_RUN_NUMBER", "")
    github_repository = os.getenv("GITHUB_REPOSITORY", "")
    github_actor = os.getenv("GITHUB_ACTOR", "")
    github_step_summary = os.getenv("GITHUB_STEP_SUMMARY")

    # Detect if running in GitHub Actions
    is_github_actions = bool(github_run_id)

    # Detect if running in interactive terminal
    is_interactive = sys.stdin.isatty()

    # Build run URL
    run_url = ""
    if github_repository and github_run_id:
        run_url = f"https://github.com/{github_repository}/actions/runs/{github_run_id}"

    return Context(
        commit_sha=github_sha,
        workflow_name=github_workflow,
        job_name=github_job,
        run_id=github_run_id,
        run_number=github_run_number,
        repository=github_repository,
        actor=github_actor,
        run_url=run_url,
        is_github_actions=is_github_actions,
        is_interactive=is_interactive,
        step_summary_path=github_step_summary,
    )
```

**Important:** Always check `is_github_actions` before writing to GitHub-specific paths.

---

### 4. Configuration System (`core/config.py`)

**Key Pattern:** Merge configuration from multiple sources with priority order

```python
import os
import yaml
from pathlib import Path
from typing import Dict, Any


def load_config(args) -> Dict[str, Any]:
    """Load configuration with priority: CLI > env > config.yaml"""

    config = {
        "storage": "artifact",
        "artifact": {"prefix": "ci-data"},
        "report": {"generate_final_report": True},
        "summary": {"include_artifacts": True},
    }

    # Load from config.yaml
    config_path = args.config or os.getenv("CI_CONFIG_PATH") or ".ci/config.yaml"
    if Path(config_path).exists():
        with open(config_path, "r") as f:
            yaml_config = yaml.safe_load(f)
            if yaml_config:
                config = deep_merge(config, yaml_config)

    # Override with environment variables
    if os.getenv("CI_STORAGE"):
        config["storage"] = os.getenv("CI_STORAGE")

    # Override with CLI arguments
    if args.storage:
        config["storage"] = args.storage

    return config


def deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
```

**Important:** Use deep merging to handle nested configuration properly.

---

### 5. Storage Interface (`core/storage.py`)

**Key Pattern:** Abstract interface with backend registration

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List


class StorageBackend(ABC):
    """Abstract storage backend interface."""

    @abstractmethod
    def save_workflow_result(self, result: Dict[str, Any]) -> None:
        """Save workflow result."""
        pass

    @abstractmethod
    def get_commit_results(self, commit: str) -> List[Dict[str, Any]]:
        """Get all results for a commit."""
        pass

    @abstractmethod
    def save_state(self, key: str, data: Dict[str, Any]) -> None:
        """Save arbitrary state."""
        pass

    @abstractmethod
    def get_state(self, key: str) -> Dict[str, Any]:
        """Get arbitrary state."""
        pass

    @abstractmethod
    def list_results(self, commit: str) -> List[str]:
        """List result keys for a commit."""
        pass

    @abstractmethod
    def store_report(self, workflow_name: str, report: Dict[str, Any]) -> None:
        """Store workflow report."""
        pass

    @abstractmethod
    def load_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Load all workflow states."""
        pass


# Backend registry
_BACKENDS = {}


def register_backend(name: str, backend_class):
    """Register a storage backend."""
    _BACKENDS[name] = backend_class


def get_backend(name: str, config: Dict) -> StorageBackend:
    """Get a storage backend instance."""
    if name not in _BACKENDS:
        raise ValueError(f"Unknown storage backend: {name}")
    return _BACKENDS[name](config)


# Register artifact backend
from storage.artifact_backend import ArtifactBackend

register_backend("artifact", ArtifactBackend)
```

**Important:** All modules must use the storage interface, never direct file I/O.

---

### 6. Artifact Backend (`storage/artifact_backend.py`)

**Key Pattern:** Write to local directory, rely on GitHub upload

```python
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List
from core.storage import StorageBackend


class ArtifactBackend(StorageBackend):
    """GitHub artifact-based storage backend."""

    def __init__(self, config: Dict):
        self.config = config
        self.base_dir = Path(config.get("artifact", {}).get("prefix", "ci-data"))
        self.results_dir = self.base_dir / "results"
        self.state_dir = self.base_dir / "state"

        # Create directories
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def save_workflow_result(self, result: Dict[str, Any]) -> None:
        """Save workflow result to results directory."""
        workflow = result.get("workflow", "unknown")
        filename = self.results_dir / f"{workflow}.json"

        with open(filename, "w") as f:
            json.dump(result, f, indent=2)

    def get_commit_results(self, commit: str) -> List[Dict[str, Any]]:
        """Get all results for a commit."""
        results = []
        for file in self.results_dir.glob("*.json"):
            with open(file, "r") as f:
                data = json.load(f)
                if data.get("commit") == commit:
                    results.append(data)
        return results

    def save_state(self, key: str, data: Dict[str, Any]) -> None:
        """Save state to state directory."""
        filename = self.state_dir / f"{key}.json"
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

    def get_state(self, key: str) -> Dict[str, Any]:
        """Get state from state directory."""
        filename = self.state_dir / f"{key}.json"
        if filename.exists():
            with open(filename, "r") as f:
                return json.load(f)
        return {}

    def list_results(self, commit: str) -> List[str]:
        """List result keys for a commit."""
        results = []
        for file in self.results_dir.glob("*.json"):
            with open(file, "r") as f:
                data = json.load(f)
                if data.get("commit") == commit:
                    results.append(file.stem)
        return results

    def store_report(self, workflow_name: str, report: Dict[str, Any]) -> None:
        """Store workflow report."""
        filename = self.results_dir / f"{workflow_name}_report.json"
        with open(filename, "w") as f:
            json.dump(report, f, indent=2)

    def load_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Load all workflow states."""
        states = {}
        for file in self.state_dir.glob("*.json"):
            with open(file, "r") as f:
                states[file.stem] = json.load(f)
        return states
```

**Important:** The artifact backend writes locally; GitHub Actions workflow must upload the directory as an artifact.

---

### 7. Workflow Module (`modules/workflow/workflow.py`)

**Key Pattern:** Start and finish commands that update workflow state

```python
import json
from datetime import datetime
from typing import Dict, Any
from core.context import Context
from core.storage import get_backend


def start(args, context: Context, config: Dict) -> Dict[str, Any]:
    """Start workflow tracking."""
    backend = get_backend(config["storage"], config)

    # Build workflow state
    state = {
        "workflow": args.workflow or context.workflow_name,
        "status": "running",
        "start_time": datetime.utcnow().isoformat(),
        "commit": context.commit_sha,
        "run_id": context.run_id,
        "run_url": context.run_url,
        "jobs": [],
        "reports": [],
        "errors": [],
    }

    # Save state
    backend.save_state(f"workflow-{state['workflow']}", state)

    return {
        "status": "started",
        "workflow": state["workflow"],
        "run_id": context.run_id,
    }


def finish(args, context: Context, config: Dict) -> Dict[str, Any]:
    """Finish workflow tracking."""
    backend = get_backend(config["storage"], config)

    # Load existing state
    workflow_name = args.workflow or context.workflow_name
    state = backend.get_state(f"workflow-{workflow_name}")

    if not state:
        raise ValueError(f"No state found for workflow: {workflow_name}")

    # Update state
    state["status"] = args.status or "success"
    state["completed_time"] = datetime.utcnow().isoformat()

    # Calculate duration
    start_time = datetime.fromisoformat(state["start_time"])
    end_time = datetime.fromisoformat(state["completed_time"])
    state["duration"] = (end_time - start_time).total_seconds()

    # Save updated state
    backend.save_state(f"workflow-{workflow_name}", state)

    # Save workflow result
    result = {
        "commit": state["commit"],
        "workflow": workflow_name,
        "job": context.job_name,
        "status": state["status"],
        "started_at": state["start_time"],
        "completed_at": state["completed_time"],
        "duration": state["duration"],
        "run_id": state["run_id"],
        "run_url": state["run_url"],
    }
    backend.save_workflow_result(result)

    return {
        "status": "finished",
        "workflow": workflow_name,
        "result_status": state["status"],
    }
```

**Important:** Always use `if: always()` in GitHub workflows for the finish command.

---

### 8. Summary Generator (`modules/summary/summary.py`)

**Key Pattern:** Write to GitHub job summary file

```python
from pathlib import Path
from typing import Dict, Any
from core.context import Context
from core.storage import get_backend


def generate(args, context: Context, config: Dict) -> Dict[str, Any]:
    """Generate GitHub job summary."""
    backend = get_backend(config["storage"], config)

    # Load workflow state
    workflow_name = args.workflow or context.workflow_name
    state = backend.get_state(f"workflow-{workflow_name}")

    if not state:
        raise ValueError(f"No state found for workflow: {workflow_name}")

    # Build summary markdown
    summary = f"""## CI Workflow Summary: {workflow_name}

**Status:** {state['status'].upper()}

### Timing
- **Total Duration:** {format_duration(state.get('duration', 0))}
- **Started:** {state.get('start_time', 'N/A')}
- **Completed:** {state.get('completed_time', 'N/A')}

### Results
- **Workflow:** {workflow_name}
- **Run ID:** {state.get('run_id', 'N/A')}
- **Commit:** {state.get('commit', 'N/A')}

"""

    # Add errors section if present
    if state.get("errors"):
        summary += "### Errors\n"
        for error in state["errors"]:
            summary += f"- {error.get('type', 'Unknown')}: {error.get('message', 'No message')}\n"
        summary += "\n"

    # Write to GitHub step summary
    if context.step_summary_path:
        summary_path = Path(context.step_summary_path)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_path, "a") as f:
            f.write(summary)

    return {
        "status": "generated",
        "workflow": workflow_name,
        "summary_path": context.step_summary_path,
    }


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m{secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h{minutes}m"
```

**Important:** Append to the summary file, don't overwrite it.

---

### 9. Report Aggregator (`modules/report/report.py`)

**Key Pattern:** Download artifacts, merge states, generate final report

```python
from typing import Dict, Any, List
from core.context import Context
from core.storage import get_backend


def aggregate(args, context: Context, config: Dict) -> Dict[str, Any]:
    """Aggregate all workflow results into final report."""
    backend = get_backend(config["storage"], config)

    # Load all workflow states
    all_states = backend.load_all_states()

    # Filter for current run
    run_id = args.run_id or context.run_id
    workflow_states = {}
    for key, state in all_states.items():
        if state.get("run_id") == run_id:
            workflow_states[key] = state

    # Build final report
    report = {
        "run_id": run_id,
        "commit": context.commit_sha,
        "repository": context.repository,
        "branch": context.run_url.split("/")[-2] if context.run_url else "unknown",
        "workflows": {},
        "summary": {},
    }

    # Add workflow results
    for workflow_name, state in workflow_states.items():
        report["workflows"][workflow_name] = {
            "status": state.get("status", "unknown"),
            "duration": state.get("duration", 0),
            "errors": state.get("errors", []),
        }

    # Calculate summary
    total_workflows = len(workflow_states)
    successful = sum(
        1 for s in workflow_states.values() if s.get("status") == "success"
    )
    failed = sum(1 for s in workflow_states.values() if s.get("status") == "failure")

    report["summary"] = {
        "total_workflows": total_workflows,
        "successful": successful,
        "failed": failed,
        "success_rate": (
            (successful / total_workflows * 100) if total_workflows > 0 else 0
        ),
    }

    # Save report
    backend.save_state(f"final-report-{run_id}", report)

    return report
```

**Important:** This command should run in the final aggregation workflow after all workflows complete.

---

### 10. Error Handling (`core/errors.py`)

**Key Pattern:** Centralized error handling with context

```python
import sys
import traceback
from typing import Dict, Any
from core.context import Context


class CIError(Exception):
    """Base CI tool error."""

    def __init__(self, message: str, error_type: str = "ci_error"):
        self.message = message
        self.error_type = error_type
        super().__init__(message)


class ConfigError(CIError):
    """Configuration error."""

    def __init__(self, message: str):
        super().__init__(message, "config_error")


class StorageError(CIError):
    """Storage backend error."""

    def __init__(self, message: str):
        super().__init__(message, "storage_error")


class ModuleError(CIError):
    """Module execution error."""

    def __init__(self, message: str):
        super().__init__(message, "module_error")


def handle_error(error: Exception, context: Context, config: Dict) -> None:
    """Handle errors and log appropriately."""
    error_info = {
        "type": type(error).__name__,
        "message": str(error),
        "traceback": traceback.format_exc() if config.get("debug") else None,
        "context": {
            "workflow": context.workflow_name,
            "run_id": context.run_id,
            "commit": context.commit_sha,
        },
    }

    # Log to stderr
    print(f"ERROR: {error}", file=sys.stderr)

    if config.get("debug"):
        print(error_info["traceback"], file=sys.stderr)

    # Write to job summary if in GitHub Actions
    if context.is_github_actions and context.step_summary_path:
        from pathlib import Path

        summary_path = Path(context.step_summary_path)
        with open(summary_path, "a") as f:
            f.write(
                f"\n### Error\n**Type:** {error_info['type']}\n**Message:** {error_info['message']}\n"
            )
```

**Important:** Always capture errors and write them to job summaries for easy debugging.

---

### 11. Bootstrap Timing Script (`scripts/ci-bootstrap.sh`)

**Key Pattern:** Shell script for early timing before Python

```bash
#!/bin/bash
# ci-bootstrap.sh - Bootstrap timing for CI workflows

set -e

# Create state directory
mkdir -p .ci/state

# Record bootstrap timestamp
BOOTSTRAP_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Build bootstrap state
cat > .ci/state/bootstrap.json << EOF
{
  "bootstrap_time": "$BOOTSTRAP_TIME",
  "workflow": "${GITHUB_WORKFLOW:-unknown}",
  "job": "${GITHUB_JOB:-unknown}",
  "run_id": "${GITHUB_RUN_ID:-unknown}",
  "run_number": "${GITHUB_RUN_NUMBER:-unknown}",
  "commit": "${GITHUB_SHA:-unknown}",
  "repository": "${GITHUB_REPOSITORY:-unknown}",
  "actor": "${GITHUB_ACTOR:-unknown}",
  "ref": "${GITHUB_REF:-unknown}",
  "event": "${GITHUB_EVENT_NAME:-unknown}",
  "runner": "${RUNNER_NAME:-unknown}",
  "os": "$(uname -s) $(uname -r)"
}
EOF

echo "Bootstrap complete at $BOOTSTRAP_TIME"
```

**Important:** This script runs before Python setup in GitHub workflows.

---

## GITHUB WORKFLOW INTEGRATION

### Example Workflow Structure

```yaml
# .github/workflows/build.yaml
name: Build

on:
  workflow_call:
    inputs:
      ref:
        required: false
        type: string

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          ref: ${{ inputs.ref }}

      - name: Bootstrap Timing
        run: |
          chmod +x tools/ci/scripts/ci-bootstrap.sh
          tools/ci/scripts/ci-bootstrap.sh

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install CI Tool
        run: |
          pip install -r tools/ci/requirements.txt

      - name: Start Workflow
        run: |
          python tools/ci/ci.py workflow start --workflow build

      - name: Run Build
        run: |
          # Your build commands here
          make build

      - name: Parse Results
        run: |
          python tools/ci/ci.py artifacts collect

      - name: Generate Summary
        run: |
          python tools/ci/ci.py summary generate --workflow build

      - name: Finish Workflow
        if: always()
        run: |
          python tools/ci/ci.py workflow finish --workflow build --status ${{ job.status }}

      - name: Upload CI State
        uses: actions/upload-artifact@v4
        with:
          name: ci-state-build
          path: ci-data/
          retention-days: 30
```

---

## TESTING STRATEGY

### Unit Tests Structure

```
tests/unit/ci/
├── test_cli.py
├── test_context.py
├── test_config.py
├── test_storage.py
├── modules/
│   ├── test_workflow.py
│   ├── test_summary.py
│   └── test_report.py
```

### Mock Storage Backend

```python
# tests/unit/ci/conftest.py
import pytest
from unittest.mock import Mock
from core.storage import StorageBackend


class MockStorageBackend(StorageBackend):
    def __init__(self):
        self.results = {}
        self.states = {}

    def save_workflow_result(self, result):
        self.results[result["workflow"]] = result

    def get_commit_results(self, commit):
        return [r for r in self.results.values() if r.get("commit") == commit]

    # ... implement other methods
```

---

## IMPLEMENTATION CHECKLIST

When implementing in code mode, follow this order:

1. ✅ Create project structure
2. ✅ Implement core CLI parsing
3. ✅ Implement context builder
4. ✅ Implement configuration system
5. ✅ Implement storage interface
6. ✅ Implement artifact backend
7. ✅ Implement workflow module
8. ✅ Implement summary generator
9. ✅ Implement report aggregator
10. ✅ Implement error handling
11. ✅ Create bootstrap script
12. ✅ Write tests
13. ✅ Update GitHub workflows

---

## KEY GOTCHAS TO WATCH FOR

1. **Always use `if: always()`** for finish commands in GitHub workflows
2. **Append to job summary**, don't overwrite
3. **Check `is_github_actions`** before writing to GitHub-specific paths
4. **Use absolute paths** for artifact upload
5. **Handle missing state gracefully** - don't crash if workflow state doesn't exist
6. **Validate workflow names** - avoid special characters in filenames
7. **Clean up on error** - ensure partial state doesn't break subsequent runs
8. **Test both GitHub and local modes** - tool should work locally too

---

## NEXT STEPS

When you switch to code mode, start with:
1. Create the directory structure
2. Implement `core/cli.py` first (foundation)
3. Then `core/context.py` and `core/config.py`
4. Then storage interface and artifact backend
5. Then module implementations
6. Finally, integration tests and workflow updates
