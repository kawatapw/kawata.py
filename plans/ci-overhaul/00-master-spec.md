# CI Tool Overhaul — Master Specification

## 1. Vision

Rewrite `tools/ci` from scratch as a clean, well-architected CI orchestration tool that:

- **Produces concise, informative summaries** — both in GitHub Actions step summaries and as PR comments
- **Parses test/lint/security results** and presents them in a structured, collapsible format that doesn't waste space
- **Works seamlessly in CI and locally** — same tool, same output, whether run in GitHub Actions or on a developer's machine
- **Is extensible** — plugin-based parser system, clean storage abstraction, configurable output
- **Reduces boilerplate** — provides a composite Action wrapper so workflow YAML is minimal

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     CLI Layer (typer)                    │
│  ci init | ci run | ci summary | ci report | ci comment  │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                   Orchestration Layer                     │
│  Job Runner (parallel + DAG)  │  Config Manager           │
└────────┬──────────────────┬─────────────────────────────┘
         │                  │
┌────────▼──────┐  ┌───────▼──────────┐  ┌────────────────┐
│  Parser Layer │  │  Storage Layer   │  │  GitHub Layer  │
│  (plugins)    │  │  (abstraction)   │  │  (API client)  │
└────────┬──────┘  └───────┬──────────┘  └───────┬────────┘
         │                 │                     │
┌────────▼─────────────────▼─────────────────────▼────────┐
│                    Output Layer                           │
│  Summary Renderer  │  Report Builder  │  PR Commenter     │
└─────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Responsibility |
|-------|---------------|
| **CLI** | Argument parsing, command dispatch, help text. Uses `typer` for modern CLI with auto-generated help. |
| **Orchestration** | Job execution with DAG-based parallelism, configuration loading and validation, lifecycle management. |
| **Parser** | Plugin-based system for reading test/lint/security output files and producing structured result data. |
| **Storage** | Abstract interface for persisting workflow state, results, and reports. File-based backend default. |
| **GitHub** | GitHub API client for PR comments, check runs, and repository context detection. |
| **Output** | Rendering summaries (markdown), building aggregate reports, posting/updating PR comments. |

## 3. Key Design Principles

1. **Typed everything** — All data models are Pydantic models or `@dataclass`. No raw dicts passed between layers.
2. **Plugin-first parsers** — Every parser is a plugin. Built-in parsers ship as default plugins. Custom parsers load from config.
3. **Storage abstraction** — Clean interface with file-based default. Swappable for DB/S3 later without touching business logic.
4. **Config discovery** — Sensible defaults for everything. Config in `pyproject.toml` under `[tool.ci]`. `ci init` scaffolds it.
5. **Local-first design** — Every feature works locally without GitHub context. GitHub integration is additive, not required.
6. **Concise output** — Summaries use collapsible `<details>` sections. Job status table at top. No redundant information.

## 4. Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| CLI framework | `typer` | Modern, type-annotated, auto-help, good subcommand support |
| Data models | `pydantic` v2 | Validation, serialization, schema generation |
| Config parsing | `pyproject.toml` via `tomllib` (stdlib) | No extra deps, standard Python practice |
| Templates | `jinja2` | Already used, well-supported, GitHub markdown compatible |
| Storage | `pathlib` + JSON files | Simple, debuggable, no external dependencies |
| GitHub API | `httpx` | Modern async-capable HTTP client, simpler than `requests` |
| Parallelism | `asyncio` + `asyncio.TaskGroup` | Stdlib, no extra deps, sufficient for subprocess parallelism |
| Testing | `pytest` + `respx` (HTTP mocking) | Consistent with project conventions |

## 5. Directory Structure

```
tools/ci/
├── pyproject.toml              # Package definition, dependencies
├── README.md
├── action.yml                  # Composite GitHub Action definition
├── src/
│   └── ci_tool/
│       ├── __init__.py
│       ├── __main__.py         # Entry: python -m ci_tool
│       ├── cli.py              # Typer app, command definitions
│       ├── config.py           # Config models, loading, validation
│       ├── context.py          # Runtime environment detection
│       ├── storage/
│       │   ├── __init__.py     # StorageBackend ABC
│       │   ├── file_backend.py # JSON file storage
│       │   └── models.py       # State/result data models
│       ├── parsers/
│       │   ├── __init__.py     # Parser base class, registry
│       │   ├── models.py       # Parsed result models
│       │   ├── pytest.py
│       │   ├── mypy.py
│       │   ├── ruff.py
│       │   ├── ty.py
│       │   ├── bandit.py
│       │   ├── trivy.py
│       │   └── safety.py
│       ├── runner/
│       │   ├── __init__.py     # Job runner with DAG + parallelism
│       │   ├── models.py       # Job definition models
│       │   └── executor.py     # Subprocess execution
│       ├── github/
│       │   ├── __init__.py     # GitHub API client
│       │   ├── models.py       # Check run, PR comment models
│       │   └── comments.py     # PR comment find/create/update
│       └── output/
│           ├── __init__.py
│           ├── summary.py      # Step summary renderer
│           ├── report.py       # Aggregate report builder
│           ├── models.py       # Output data models
│           └── templates/
│               ├── summary.md.j2
│               └── report.md.j2
└── tests/
    ├── conftest.py
    ├── test_cli.py
    ├── test_config.py
    ├── test_context.py
    ├── test_storage.py
    ├── test_parsers.py
    ├── test_runner.py
    └── test_output/
        ├── test_summary.py
        └── test_report.py
```

## 6. Configuration Schema

Config lives in `pyproject.toml` under `[tool.ci]`:

```toml
[tool.ci]
# Storage backend (currently only "file")
storage = "file"

[tool.ci.storage.file]
# Directory for state and results
directory = ".ci-data"

[tool.ci.summary]
# What to include in summaries
include_jobs = true
include_timing = true
include_artifacts = true
max_failures_shown = 5
max_code_snippet_lines = 8

[tool.ci.comment]
# PR comment behavior
enabled = true
update_existing = true
include_job_table = true
include_failures = true
include_code_snippets = true

[tool.ci.jobs]
# Job definitions for `ci run`

[tool.ci.jobs.test]
command = "uv run pytest tests/ --junit-xml=reports/junit.xml"
report = "reports/junit.xml"
parser = "pytest"

[tool.ci.jobs.lint]
command = "uv run ruff check . --output-file reports/ruff.json --output-format json"
report = "reports/ruff.json"
parser = "ruff"

[tool.ci.jobs.typecheck]
command = "uv run mypy . > reports/mypy.txt 2>&1 || true"
report = "reports/mypy.txt"
parser = "mypy"

[tool.ci.jobs.security]
command = "uv run bandit -r . -f json -o reports/bandit.json || true"
report = "reports/bandit.json"
parser = "bandit"
```

The `ci init` command generates this with all defaults so users can discover every option.

## 7. CLI Command Reference

```
ci init                    Scaffold [tool.ci] in pyproject.toml with all defaults
ci run [jobs...]           Run configured jobs with DAG parallelism, then summarize
ci summary                 Parse existing reports and generate summary
ci report                  Aggregate all job results into final report
ci comment                 Post/update PR comment with summary
ci config                  Show resolved configuration
ci doctor                  Validate setup: check commands, parsers, storage
```

### `ci run` flags

```
--jobs TEXT            Specific jobs to run (default: all)
--parallel/--serial    Execution mode (default: parallel per DAG)
--summary/--no-summary Generate summary after run (default: true)
--comment/--no-comment Post PR comment after run (default: false)
```

### `ci summary` flags

```
--dir TEXT       Directory containing report files (default: ./reports)
--output TEXT    Output file (default: stdout / GITHUB_STEP_SUMMARY)
--format TEXT    Output format: markdown, json (default: markdown)
```

## 8. Summary Output Design

The summary uses GitHub-flavored markdown with `<details>`/`<summary>` for collapsible sections:

```markdown
## CI Summary

| Job | Status | Duration | Summary |
|-----|--------|----------|---------|
| test | PASS | 45s | 142 passed, 3 failed |
| lint | PASS | 12s | 0 violations |
| typecheck | FAIL | 30s | 2 errors |
| security | PASS | 8s | 0 issues |

**Commit:** `abc123d` | **Duration:** 1m35s | **Overall:** FAIL

<details><summary>FAIL typecheck — 2 errors</summary>

**`app/main.py:42`** — error: Argument 1 has incompatible type "str"; expected "int" [arg-type]

```
  40 | def process(value: int) -> None:
  41 |     ...
> 42 | process(user_input)  # type: ignore
  43 |
```

**`app/utils.py:15`** — error: Name "result" is not defined [name-defined]

```
  13 | def calculate():
  14 |     x = 1
> 15 |     return result
  16 |
```

</details>

<details><summary>FAIL test — 3 failed</summary>

**`tests/test_auth.py::test_login`** — AssertionError: Expected 200, got 401

```
   def test_login():
       resp = client.post("/login", data={"user": "test"})
>      assert resp.status_code == 200
E      AssertionError: 401
```

</details>
```

## 9. Implementation Phases

| Phase | Spec File | Scope |
|-------|-----------|-------|
| 1 — Core | `01-core-framework.md` | CLI, config, context, storage, data models |
| 2 — Parsers | `02-parser-system.md` | Parser plugin system, all built-in parsers |
| 3 — Runner | `03-job-runner.md` | Job execution with DAG + parallelism |
| 4 — Output | `04-output-layer.md` | Summary renderer, report builder, templates |
| 5 — GitHub | `05-github-integration.md` | GitHub API, PR comments, check runs |
| 6 — Action | `06-composite-action.md` | Composite Action wrapper, action.yml |

Each phase is a self-contained spec that the AI can implement independently. Phases build on each other in order.
