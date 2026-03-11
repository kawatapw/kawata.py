# CI TOOL IMPLEMENTATION CONTEXT
Authoritative specification for implementing the modular CI toolkit located in `tools/ci`.

This tool is intended to extend GitHub Actions workflows with advanced CI orchestration capabilities including:

- workflow lifecycle tracking
- job summary generation
- artifact-based state storage
- report aggregation
- future Discord integration
- future backend API storage
- repository management tooling
- deployment utilities
- interactive TUI usage

The design must emphasize **robust modular extensibility**. New features should be added via modules without modifying the core framework.

---

# PRIMARY GOALS

The CI tool must:

1. Provide a **unified CLI interface** for CI automation.
2. Be **fully modular** so new modules can be added without modifying core code.
3. Support **multiple storage backends**.
4. Generate **GitHub job summaries** automatically.
5. Track workflow execution across multiple workflows.
6. Aggregate results into **final CI reports**.
7. Operate correctly **inside GitHub Actions environments**.
8. Be usable **locally by developers**.
9. Provide a foundation for **interactive TUI usage** later.

---

# HIGH LEVEL SYSTEM OVERVIEW

The CI toolkit acts as an orchestration layer between GitHub workflows and future backend services.

System responsibilities:

- workflow lifecycle tracking
- workflow result recording
- artifact inspection
- CI report generation
- job summary generation
- cross-workflow state tracking
- extensible repo management commands

Future capabilities:

- Discord CI messaging
- CI dashboards
- deployment management
- server automation
- container management
- repo maintenance tools
- performance reporting
- test aggregation
- PP recalculation orchestration

---

# TOOL LOCATION

The tool must exist inside the repository at:

```
tools/ci/
```

---

# CORE DESIGN PRINCIPLES

## 1. Modular Architecture

The system must be built using a **plugin-style module system**.

Modules must be loaded dynamically.

New functionality should be implemented by adding modules rather than editing core code.

Example module categories:

- workflow modules
- summary modules
- reporting modules
- deployment modules
- repository management modules
- Discord modules
- CI monitoring modules

---

## 2. CLI Command Architecture

The CLI must follow this structure:

```
ci <module> <action> [arguments]
```

Examples:

```
ci workflow start
ci workflow finish
ci summary generate
ci report aggregate
ci artifacts collect
ci deploy server
ci repo cleanup
```

CLI behavior requirements:

- Unknown module → clear error
- Unknown action → clear error
- Commands must support `--help`
- Commands must support `--json` output where possible
- CLI must support global flags

Example global flags:

```
--storage
--config
--verbose
--debug
--json
```

---

# CLI ENTRYPOINT

Primary executable:

```
tools/ci/ci.py
```

Responsibilities:

- parse CLI arguments
- resolve modules
- load module implementations
- pass arguments to module actions
- handle errors centrally
- provide global logging
- detect interactive terminal for TUI launch

If no arguments are provided and terminal is interactive:

Launch the **TUI mode**.

---

# INTERACTIVE MODE (FUTURE SUPPORT)

If `ci` is executed with no arguments inside a terminal:

```
ci
```

The tool must detect interactive execution and launch a TUI interface.

The architecture must support this later without requiring major refactoring.

Potential TUI features:

- view CI status
- browse reports
- inspect artifacts
- run CI tasks locally
- trigger repo tools

This does not need to be implemented immediately but the architecture must allow it.

---

# CONFIGURATION SYSTEM

Configuration priority order:

1. CLI arguments
2. environment variables
3. config.yaml fallback

Config file location:

```
.ci/config.yaml
```

Example config:

```
storage: artifact

artifact:
  prefix: ci-data

report:
  generate_final_report: true

summary:
  include_artifacts: true
```

Configuration must support deep merging.

---

# GITHUB ENVIRONMENT DETECTION

The tool must automatically detect when it is running inside GitHub Actions.

Important environment variables:

```
GITHUB_SHA
GITHUB_WORKFLOW
GITHUB_JOB
GITHUB_RUN_ID
GITHUB_RUN_NUMBER
GITHUB_REPOSITORY
GITHUB_ACTOR
GITHUB_STEP_SUMMARY
```

A context parser must extract this information into a structured object.

---

# CONTEXT OBJECT

All modules should receive a shared context object.

Example fields:

```
commit_sha
workflow_name
job_name
run_id
run_number
repository
actor
run_url
is_github_actions
```

Run URL example:

```
https://github.com/{repo}/actions/runs/{run_id}
```

---

# WORKFLOW LIFECYCLE SYSTEM

Each workflow must report lifecycle events.

Two commands must exist:

```
ci workflow start
ci workflow finish
```

### Workflow Start

Records:

- workflow name
- job name
- commit
- start time
- run id

Status becomes:

```
running
```

---

### Workflow Finish

Records:

- completion time
- duration
- status

Possible statuses:

```
success
failure
cancelled
skipped
```

Finish must run with:

```
if: always()
```

inside GitHub workflows.

---

# RESULT MODEL

Each workflow produces a result object.

Example result:

```
{
  "commit": "abc123",
  "workflow": "build",
  "job": "compile",
  "status": "success",
  "started_at": "...",
  "completed_at": "...",
  "duration": 153,
  "run_id": 123456,
  "run_url": "https://github.com/org/repo/actions/runs/123456"
}
```

---

# STORAGE SYSTEM

Storage must be fully abstracted.

Modules must not directly read/write files.

Instead they call the storage interface.

---

# STORAGE INTERFACE

Required methods:

```
save_workflow_result(result)
get_commit_results(commit)
save_state(key,data)
get_state(key)
list_results(commit)
```

---

# STORAGE BACKENDS

Initial implementation:

```
artifact
```

Future implementations:

```
api
database
redis
filesystem
```

Backend selected via:

```
--storage
```

or config.yaml.

---

# ARTIFACT STORAGE DESIGN

Artifact storage writes data locally then relies on GitHub artifact upload steps.

Local storage directory:

```
ci-data/
```

Structure:

```
ci-data/
   results/
      build.json
      lint.json
      test.json

   state/
      workflow-start.json
```

Each workflow writes its own result file to avoid conflicts.

Artifact name pattern:

```
ci-data-${GITHUB_SHA}
```

Artifacts are uploaded by workflows using:

```
actions/upload-artifact
```

Retention period default:

30 days.

---

# REPORT AGGREGATION

The system must support aggregated CI reports.

Command:

```
ci report aggregate
```

Process:

1. load workflow results
2. merge results
3. generate final report

Output:

```
ci-report.md
```

Example:

```
Commit: abc123

Workflow Status

prep-build   success
build        success
lint         success
test         failure
```

---

# JOB SUMMARY GENERATION

GitHub job summaries must be supported.

Command:

```
ci summary generate
```

The module writes to:

```
$GITHUB_STEP_SUMMARY
```

The summary must include:

- workflow name
- status
- duration
- artifacts
- parsed report results
- tool warnings/errors

Summaries must be readable and well formatted.

---

# ERROR HANDLING

The tool must capture internal errors.

Errors must appear inside job summaries so CI failures are easy to diagnose.

Error categories:

```
configuration errors
parsing errors
report generation errors
storage errors
module errors
```

---

# PRE-WORKFLOW TIMING TOOL

A small helper tool must exist for timing workflows before Python executes.

Purpose:

Measure time spent in early workflow steps such as:

- checkout
- dependency setup

Example usage:

```
ci-timer start
```

Later:

```
ci workflow start
```

Timer data should be passed into workflow results.

Implementation can be shell-based.

---

# MODULE SYSTEM

Modules must exist in:

```
tools/ci/modules/
```

Example modules:

```
workflow
summary
report
artifacts
discord
deploy
repo
```

Each module exposes actions.

Example:

```
modules/workflow/workflow.py

start()
finish()
```

---

# TEMPLATE SYSTEM

Markdown templates must be supported.

Template directory:

```
tools/ci/templates/
```

Examples:

```
workflow_summary.md
ci_report.md
```

Templates allow customization of generated output.

---

## GitHub Workflow Integration Design

This CI tool must integrate seamlessly with a repository using a **master orchestrator workflow** (`1-master.yaml`) that triggers reusable workflows:

- prep-build
- build
- lint
- dep-scan
- sec-scan
- test
- release
- publish
- sync-docs

Each workflow executes independently but contributes data to a **shared CI state artifact system**.

---

# Core Integration Model

Each workflow will follow the same integration pattern:

1. Early timing bootstrap (shell tool)
2. CI tool initialization
3. Workflow execution
4. CI tool report parsing
5. Artifact state update
6. Step summary generation

Example conceptual workflow structure:

```
bootstrap -> ci start -> run actual tasks -> ci parse results -> ci summarize -> ci upload state
```

This ensures:

- All workflows are tracked uniformly
- Failures are captured even when intermediate steps fail
- Data can be aggregated later

---

# Bootstrap Timing Tool

A minimal shell script runs **before Python setup**.

Purpose:

- Record earliest possible start timestamp
- Capture checkout time
- Capture runner startup delay
- Generate initial state metadata

Example responsibilities:

```
ci-bootstrap.sh
```

Responsibilities:

Record:

- workflow start timestamp
- job start timestamp
- runner name
- OS
- workflow name
- commit SHA
- branch
- event type

Output:

```
.ci/state/bootstrap.json
```

This file becomes the **base state object** for the workflow.

---

# CI Tool Execution

After bootstrap:

```
python ci-tool start --workflow build
```

Responsibilities:

Initialize workflow state

Create directory:

```
.ci/state/
```

Example state file:

```
.ci/state/workflow-build.json
```

Structure example:

```
{
  "workflow": "build",
  "status": "running",
  "start_time": "...",
  "jobs": [],
  "reports": [],
  "errors": []
}
```

---

# Artifact Storage Backend

Temporary persistence will use **GitHub Artifacts**.

Each workflow uploads:

```
ci-state-${workflow}
```

Artifact contents:

```
.ci/state/
```

This allows other workflows (especially `summarize.yaml`) to download and aggregate the state.

Example artifact layout:

```
ci-state-build
  workflow-build.json

ci-state-lint
  workflow-lint.json

ci-state-test
  workflow-test.json
```

Artifacts are temporary but sufficient for CI run lifetime.

Future backends may include:

- Kawata backend API
- S3 compatible storage
- Redis
- local state server
- database storage

The storage system must support **backend modules**.

---

# Storage Backend Interface

All persistence mechanisms must implement a unified interface:

```
class StorageBackend:

    def store_state(workflow_name, state_data)

    def load_state(workflow_name)

    def list_workflows()

    def store_report(workflow_name, report)

    def load_all_states()
```

Artifact backend responsibilities:

- compress state directory
- upload artifact
- download artifacts
- merge state files

---

# Workflow Report Parsing

Each workflow produces reports that the CI tool parses.

Supported report types include:

Build logs

Lint reports

Test reports (pytest, junit)

Security scan reports

Dependency scan reports

Custom JSON reports

Reports will be registered via plugin modules.

Example parser registry:

```
parsers/
  pytest_parser.py
  bandit_parser.py
  pip_audit_parser.py
  generic_log_parser.py
```

Each parser implements:

```
parse(report_path) -> structured_report
```

Structured report example:

```
{
  "type": "test",
  "passed": 120,
  "failed": 3,
  "skipped": 5,
  "duration": 24.3
}
```

---

# Job Summary Generation

Each workflow generates a **GitHub job summary**.

The CI tool will write to:

```
$GITHUB_STEP_SUMMARY
```

Example summary sections:

```
## CI Workflow Summary: Build

Status: Success

### Timing
Total Duration: 2m14s
Checkout: 18s
Build: 1m56s

### Results
Artifacts Produced: 3
Warnings: 2
Errors: 0
```

For test workflows:

```
### Test Results
Passed: 120
Failed: 3
Skipped: 5
Coverage: 84%
```

For lint workflows:

```
### Lint Issues
Errors: 0
Warnings: 6
Files Affected: 4
```

---

# Error Handling

The CI tool must capture and report errors even when steps fail.

Error sources include:

- parsing failures
- tool crashes
- malformed reports
- missing artifacts

Errors are stored in workflow state:

```
"errors": [
  {
    "type": "parser_error",
    "tool": "pytest",
    "message": "...",
    "file": "report.xml"
  }
]
```

Summaries must include an **Errors section** when present.

---

# Final Aggregation Workflow

The `summarize.yaml` workflow downloads all state artifacts.

It runs:

```
ci-tool aggregate --run-id $RUN_ID
```

Responsibilities:

Download artifacts:

```
ci-state-build
ci-state-lint
ci-state-test
ci-state-dep-scan
ci-state-sec-scan
```

Merge all state files.

Generate a **final global summary**.

Example:

```
# CI Run Summary

Commit: abc123
Branch: BE-Master

## Workflow Results

Build: SUCCESS
Lint: SUCCESS
Dependency Scan: SUCCESS
Security Scan: WARNING
Tests: FAILED

## Test Summary
Passed: 120
Failed: 3
Skipped: 5

## Security Issues
High: 0
Medium: 1
Low: 3

## Timing
Total CI Duration: 9m42s
```

This summary is written to:

```
$GITHUB_STEP_SUMMARY
```

inside the final job.

---

# Workflow Compatibility Requirements

The CI tool must work with:

push events

pull requests

manual workflow_dispatch

workflow_call reusable workflows

branch and tag builds

The tool must rely on environment variables:

```
GITHUB_RUN_ID
GITHUB_SHA
GITHUB_REF
GITHUB_EVENT_NAME
GITHUB_WORKFLOW
GITHUB_JOB
GITHUB_ACTOR
```

These values become part of the CI state metadata.

---

# sync-docs Workflow Integration

The `sync-docs` workflow can optionally integrate with the CI tool.

If enabled it may record:

Documentation update events

Wiki sync success/failure

Changed documentation files

Example state entry:

```
{
  "workflow": "sync-docs",
  "docs_updated": 12,
  "wiki_sync": "success"
}
```

---

# Design Goals for Robustness

The CI tool must be designed to support future capabilities without modifying core systems.

Required architectural characteristics:

Plugin-based modules

Storage backend abstraction

Report parser registry

Workflow state schema versioning

Fault tolerant execution

Graceful handling of missing reports

Independent workflow operation

Future expansion areas include:

deployment orchestration

docker image builds

server provisioning

performance benchmarking

osu! server utilities

backend management tools

This ensures the CI tool becomes a **general automation platform for repository and infrastructure management**, not just a CI summarization utility.

# DEVELOPMENT PRIORITY

Implementation order:

1. CLI framework
2. context parser
3. module loader
4. workflow module
5. storage interface
6. artifact backend
7. summary generator
8. report aggregator
9. configuration system
10. timer tool

---

# EXTENSIBILITY REQUIREMENTS

Future features must be implementable without core refactoring.

Examples:

- Discord notification module
- backend storage module
- deployment automation
- repo maintenance commands
- docker orchestration
- PP recalculation tools
- CI dashboard generator

---

# SECURITY CONSIDERATIONS

The CI tool must never expose internal infrastructure.

Data storage must remain internal to the repository or CI environment unless explicitly configured.

---

# FINAL EXPECTED RESULT

A robust CI framework that:

- extends GitHub Actions
- tracks workflow state
- generates summaries
- stores CI data via artifacts
- supports future backend integration
- supports modular feature expansion
- supports interactive developer usage