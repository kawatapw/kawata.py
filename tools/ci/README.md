## CI Orchestration Tool (`tools/ci`)

This directory contains a small, composable CI orchestration tool that runs inside GitHub Actions (and can also be used locally) to:

- Track workflow lifecycle timing and status
- Collect and summarize artifacts (tests, lint, security, coverage)
- Generate rich GitHub job summaries
- Aggregate results from multiple workflows into a final CI report

The main entrypoint is `ci.py`, which exposes a `ci`-style CLI.

---

## Installation

From the repository root, install dependencies (Python 3.11+ recommended):

```bash
pip install -r tools/ci/requirements.txt
```

You can then invoke the tool directly:

```bash
python tools/ci/ci.py --help
```

In GitHub Actions, the tool is typically installed in a dedicated step:

```yaml
- name: Install CI Tool
  run: |
    pip install -r tools/ci/requirements.txt
```

---

## CLI Overview

The CLI is structured as:

```bash
python tools/ci/ci.py [GLOBAL FLAGS] <module> <action> [ARGS...]
```

**Global flags**:

- `--storage` – storage backend (default: `artifact`)
- `--config` – path to config file (default: `.ci/config.yaml`, or `CI_CONFIG_PATH`)
- `--verbose` – enable verbose logging
- `--debug` – enable debug output (including tracebacks)
- `--json` – print JSON instead of human-readable output

**Modules and actions**:

- `workflow start` – start workflow or job tracking
- `workflow finish` – finish workflow or job tracking (and, at workflow level, persist result)
- `summary generate` – generate a GitHub job summary (optionally including artifacts)
- `report aggregate` – aggregate results from all workflows in a run
- `artifacts collect` – collect/download workflow artifacts (implementation-specific)

Run `python tools/ci/ci.py --help` or `python tools/ci/ci.py <module> --help` for details.

---

## Configuration

Configuration is merged from three sources (in priority order):

1. **CLI flags** (e.g. `--storage`)
2. **Environment variables** (e.g. `CI_STORAGE`, `CI_CONFIG_PATH`)
3. **YAML config file** (default: `.ci/config.yaml`)

The configuration schema is roughly:

```yaml
storage: artifact
artifact:
  prefix: ci-data          # base directory for results and state

report:
  generate_final_report: true

summary:
  include_artifacts: true
```

You can point to an alternate config file with:

```bash
python tools/ci/ci.py --config path/to/config.yaml ...
```

---

## Storage Model

By default, the tool uses the **artifact** storage backend (`storage.artifact_backend.ArtifactBackend`), which:

- Writes workflow **state** under `<prefix>/state/`
- Writes workflow **results** and reports under `<prefix>/results/`

Where `<prefix>` is `artifact.prefix` from config (default `ci-data`).

In GitHub Actions, you are expected to upload this directory as an artifact so that a later “aggregation” workflow can download and aggregate results:

```yaml
- name: Upload CI State
  uses: actions/upload-artifact@v4
  with:
    name: ci-state-build
    path: ci-data/
    retention-days: 30
```

---

## Typical GitHub Actions Usage

### 1. Bootstrap timing

Run early in the workflow, before Python setup, to capture bootstrap timing and a small amount of environment metadata:

```yaml
- name: Bootstrap Timing
  run: |
    chmod +x tools/ci/scripts/ci-bootstrap.sh
    tools/ci/scripts/ci-bootstrap.sh
```

This creates `.ci/state/bootstrap.json` with basic run metadata.

### 2. Start workflow tracking

After setting up Python and installing dependencies, start workflow tracking:

```yaml
- name: Start Workflow
  run: |
    python tools/ci/ci.py workflow start --workflow build
```

If `--workflow` is omitted, the tool will fall back to the GitHub workflow name from the environment.

In a multi-job workflow, you can also track individual jobs. For example, inside a job:

```yaml
- name: Start Job
  run: |
    python tools/ci/ci.py workflow start \
      --workflow build \
      --job linux-tests
```

If `--job` is omitted, the job name falls back to `GITHUB_JOB`.

### 3. Run your actual job

Run your build/tests/linters/etc. as usual:

```yaml
- name: Run Build
  run: |
    make build
```

You should also ensure relevant reports (e.g. `junit.xml`, `mypy.txt`, `ruff.txt`, coverage XML, security scans) are written into a directory that you later pass to `summary generate` as `--artifact-dir` (or bundle into a single artifact and unpack before summarizing).

### 4. Collect artifacts

Use the artifacts module to normalize or collect artifacts for later summarization/aggregation:

```yaml
- name: Collect Artifacts
  run: |
    python tools/ci/ci.py artifacts collect
```

The exact behavior is implementation-specific, but the intent is to gather all interesting CI outputs into a predictable structure.

### 5. Generate GitHub job summary

At the end of the job, generate a rich job summary that is written to `GITHUB_STEP_SUMMARY`:

```yaml
- name: Generate Summary
  run: |
    python tools/ci/ci.py summary generate \
      --workflow build \
      --artifact-dir path/to/downloaded/artifacts
```

The summary module will:

- Look up workflow state for the run (or gracefully mark the workflow as **SKIPPED** if it never ran)
- Print high-level timing and status
- Enumerate downloaded artifacts
- Parse standard reports using the parser registry (see below)
- Generate rich markdown output using Jinja2 templates

### Supported Report Parsers

The CI tool includes parsers for the following report formats:

| Parser | Formats | Description |
|--------|---------|-------------|
| **pytest** | JUnit XML | Test results from pytest |
| **mypy** | Text output | Type checking errors and notes |
| **ruff** | Text, JSON | Linting violations |
| **bandit** | JSON | Security scan results |
| **trivy** | SARIF, JSON | Vulnerability scan results |
| **safety** | JSON | Dependency vulnerability scan |
| **generic** | Any | Fallback for unrecognized formats |

### Parser Auto-Detection

The parser registry automatically detects the appropriate parser using:

1. **Filename patterns**: Files containing `mypy`, `ruff`, `trivy`, `safety`, `bandit`, `junit`, or `pytest` in the name
2. **File extensions**: `.xml` → pytest, `.sarif` → trivy
3. **Content analysis**: JSON files are inspected for SARIF schema, Safety structure, Bandit format, etc.

You can also explicitly specify a parser:

```bash
python tools/ci/ci.py summary generate \
  --workflow build \
  --artifact-dir path/to/artifacts \
  --parser mypy  # Force mypy parser
```

### Template System

The summary module uses Jinja2 templates for generating markdown output. The default template is located at `tools/ci/templates/workflow_summary.md`.

You can customize the template by:

1. Modifying the default template
2. Creating a custom template and specifying it via configuration

Template variables available:

- `workflow_name`: Name of the workflow
- `status`: Workflow status (SUCCESS, FAILURE, SKIPPED)
- `duration`: Formatted duration string
- `start_time`: Workflow start time
- `completed_time`: Workflow completion time
- `run_id`: GitHub Actions run ID
- `commit`: Commit SHA
- `test_results`: Formatted test results
- `lint_results`: Formatted lint results
- `security_results`: Formatted security scan results
- `coverage_results`: Formatted coverage results
- `artifacts`: List of artifact filenames
- `errors`: List of error dictionaries

### Custom Parsers

You can create custom parsers by:

1. Creating a new parser class that inherits from `Parser`
2. Implementing the `parse()` and `get_type()` methods
3. Registering the parser using `register_parser()`

Example:

```python
from modules.parsers.registry import Parser, register_parser


class MyCustomParser(Parser):
    def parse(self, content: str) -> Dict[str, Any]:
        # Parse content and return structured data
        return {"type": "custom", "summary": {...}, "data": [...]}

    def get_type(self) -> str:
        return "custom"


# Register the parser
register_parser("custom", MyCustomParser)
```

### 6. Finish workflow (always)

Always finish the workflow, even on failure, so that duration and final status are captured:

```yaml
- name: Finish Workflow
  if: always()
  run: |
    python tools/ci/ci.py workflow finish \
      --workflow build \
      --status ${{ job.status }}
```

The finish step updates workflow state, calculates duration, and writes a single per-workflow result entry.

If you are also tracking jobs, you can finish each job within its own job context:

```yaml
- name: Finish Job
  if: always()
  run: |
    python tools/ci/ci.py workflow finish \
      --workflow build \
      --job linux-tests \
      --status ${{ job.status }}
```

Job-level finishes update the job entry in the workflow state (including per-job duration) but do not emit additional workflow result records.

### 7. Upload CI state artifacts

Finally, upload `ci-data/` so a later workflow can aggregate everything:

```yaml
- name: Upload CI State
  uses: actions/upload-artifact@v4
  with:
    name: ci-state-build
    path: ci-data/
    retention-days: 30
```

---

## Aggregation Workflow (Cross-Workflow Report)

In a separate workflow (triggered after others complete, or manually), download all `ci-data` artifacts, merge them, and run the report aggregator:

```yaml
- name: Aggregate CI Reports
  run: |
    # After downloading/unpacking all ci-data/ artifacts into a single directory
    python tools/ci/ci.py report aggregate --json
```

`report aggregate`:

- Loads all workflow state for the current `run_id`
- Computes per-workflow status/duration/error counts
- Produces an overall summary (total workflows, successful, failed, success rate)
- Stores the final report via the storage backend (e.g. `final-report-<run_id>.json` in state)

You can consume this JSON directly or use it to drive additional notifications/dashboards.

---

## Local Usage

While designed around GitHub Actions, the tool can also run locally:

- `GITHUB_*` environment variables will be missing, so `Context` falls back to empty values and `is_github_actions` is `False`.
- GitHub-specific behavior (like writing to `GITHUB_STEP_SUMMARY`) is skipped.

Examples:

```bash
python tools/ci/ci.py workflow start --workflow local-test
python tools/ci/ci.py workflow finish --workflow local-test --status success
python tools/ci/ci.py report aggregate --json
```

This is useful for debugging configuration, storage, and report generation outside CI.

---

## Key Design Notes

- **Idempotent and composable**: Modules (`workflow`, `summary`, `report`, `artifacts`) are small, focused units you can mix and match per workflow.
- **Storage-agnostic**: All modules talk through the `core.storage` interface; swapping storage backends only requires configuration.
- **GitHub-aware but not GitHub-bound**: The context object understands GitHub Actions but degrades gracefully when run elsewhere.
- **Error visibility**: Errors are centralized in `core.errors` and, when possible, surfaced in GitHub job summaries for easier debugging.
- **Extensible parser system**: The parser registry supports auto-detection and custom parsers for any log format.
- **Template-based output**: Summary generation uses Jinja2 templates for flexible, customizable markdown output.
- **Comprehensive tool support**: Built-in parsers for mypy, ruff, bandit, trivy, safety, and pytest with automatic format detection.
