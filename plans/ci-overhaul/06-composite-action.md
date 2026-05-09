# Phase 6 — Composite Action Wrapper

## Scope

A composite GitHub Action that wraps the CI tool, reducing boilerplate in workflow YAML. This is the final piece — it makes the tool easy to adopt in any workflow.

## 1. Design Principles

1. **Minimal YAML** — A 3-step workflow instead of 15+ steps with repeated boilerplate.
2. **Config-driven** — The action reads from `[tool.ci]` in pyproject.toml. No separate action inputs needed for most things.
3. **Backward compatible** — Teams can still use the CLI directly if they prefer. The Action is optional sugar.
4. **Smart defaults** — Auto-detects Python version, installs uv, sets up caching.

## 2. Action Definition

### `tools/ci/action.yml`

```yaml
name: 'CI Tool'
description: 'Run CI with the ci-tool orchestrator'
author: 'ZOO'

branding:
  icon: 'check-circle'
  color: 'green'

inputs:
  python-version:
    description: 'Python version to use'
    required: false
    default: '3.11'
  jobs:
    description: 'Comma-separated list of jobs to run (default: all)'
    required: false
    default: ''
  mode:
    description: 'Execution mode: parallel or serial'
    required: false
    default: 'parallel'
  post-comment:
    description: 'Post a PR comment with results'
    required: false
    default: 'true'
  comment-on-pr:
    description: 'Only post comment on PR builds'
    required: false
    default: 'true'
  github-token:
    description: 'GitHub token for PR comments'
    required: false
    default: ${{ github.token }}

runs:
  using: 'composite'
  steps:
    - name: Setup Python
      uses: actions/setup-python@v5
      with:
        python-version: ${{ inputs.python-version }}

    - name: Install uv
      uses: astral-sh/setup-uv@v4
      with:
        enable-cache: true

    - name: Install ci-tool
      shell: bash
      run: |
        uv pip install --system ${{ github.action_path }}

    - name: Run CI
      shell: bash
      run: |
        if [ -n "${{ inputs.jobs }}" ]; then
          ci run --jobs "${{ inputs.jobs }}" --${{ inputs.mode }} --summary
        else
          ci run --${{ inputs.mode }} --summary
        fi
      env:
        GITHUB_TOKEN: ${{ inputs.github-token }}

    - name: Post PR Comment
      if: inputs.post-comment == 'true' && (inputs.comment-on-pr != 'true' || github.event_name == 'pull_request')
      shell: bash
      run: |
        ci comment
      env:
        GITHUB_TOKEN: ${{ inputs.github-token }}
```

## 3. Example Workflow Using the Action

### `.github/workflows/ci.yaml` (simplified)

```yaml
name: CI

on:
  push:
    branches: ['**']
  pull_request:
    branches: ['**']

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: ./.github/actions/ci-tool
        with:
          python-version: '3.11'
          mode: parallel
          post-comment: true
```

That's it. The entire CI workflow is 15 lines instead of 900+.

## 4. Composite Action Directory Structure

For the composite Action to work, we need to reorganize slightly:

```
tools/ci/
├── action.yml                  # Composite action definition
├── pyproject.toml              # Package definition
├── src/ci_tool/                # Source code (as defined in phases 1-5)
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py
│   ├── context.py
│   ├── storage/
│   ├── parsers/
│   ├── runner/
│   ├── github/
│   └── output/
└── tests/
```

The composite Action references `${{ github.action_path }}` which points to the `tools/ci` directory. `uv pip install` installs the package from that path.

## 5. Migration Guide

For the existing `.github/workflows/ci.yaml`:

### Before (current — 900+ lines)
- Separate jobs for initialization, build, mypy, ruff, ty, bandit, test, release, publish, final-summary
- Each job repeats: checkout, setup-python, bootstrap CI tool, start/finish workflow tracking
- Manual artifact upload/download between jobs
- Manual summary generation in each job

### After (using composite action — ~15 lines)
- Single job using the composite action
- All configuration in `pyproject.toml` under `[tool.ci]`
- PR comment posted automatically
- Summary generated automatically

### Migration steps:
1. Run `ci init` to scaffold `[tool.ci]` in pyproject.toml
2. Define jobs in `[tool.ci.jobs]` section
3. Replace workflow YAML with the composite action
4. Remove old `tools/ci` directory (backup first)
5. Test locally with `ci run`

## 6. Local Usage (without Action)

The tool works standalone for local development:

```bash
# Install
cd tools/ci && pip install -e .

# Initialize config
ci init

# Run all configured jobs
ci run

# Run specific jobs
ci run test lint

# Parse existing reports and show summary
ci summary --dir ./reports

# Show config
ci config

# Validate setup
ci doctor
```

## 7. Implementation Notes

- The composite Action uses `uv pip install --system` to install the package. This is fast and doesn't require a virtual environment.
- The `astral-sh/setup-uv` action handles uv installation with caching.
- The Action passes `GITHUB_TOKEN` explicitly for PR comment posting.
- The `ci run` command handles: job execution, report parsing, summary generation, and step summary writing.
- The `ci comment` command handles: finding the PR, finding/creating the comment, and posting the summary.
- For the existing complex workflow (with Docker build, multi-arch, release, publish), the composite Action can be used for the lint/test/security jobs, while build/release/publish remain as separate jobs.
