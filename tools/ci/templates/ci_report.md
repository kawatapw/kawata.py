# CI Report

## Run Summary

- **Run ID:** {{ run_id }}
- **Commit:** {{ commit }}
- **Repository:** {{ repository }}
- **Branch:** {{ branch }}

## Workflow Results

| Workflow | Status | Duration | Errors |
|----------|--------|----------|--------|
{% for name, workflow in workflows.items() %}
| {{ name }} | {{ workflow.status }} | {{ workflow.duration }}s | {{ workflow.errors|length }} |
{% endfor %}

## Overall Summary

- **Total Workflows:** {{ summary.total_workflows }}
- **Successful:** {{ summary.successful }}
- **Failed:** {{ summary.failed }}
- **Success Rate:** {{ summary.success_rate|round(2) }}%
