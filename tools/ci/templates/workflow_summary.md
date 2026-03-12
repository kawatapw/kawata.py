# CI Workflow Summary

## Workflow: {{ workflow_name }}

**Status:** {{ status }}

### Timing
- **Total Duration:** {{ duration }}
- **Started:** {{ start_time }}
- **Completed:** {{ completed_time }}

### Results
- **Workflow:** {{ workflow_name }}
- **Run ID:** {{ run_id }}
- **Commit:** {{ commit }}

{% if errors %}
### Errors
{% for error in errors %}
- {{ error.type }}: {{ error.message }}
{% endfor %}
{% endif %}
