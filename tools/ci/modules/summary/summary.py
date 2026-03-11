"""GitHub job summary generator."""
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List
from core.context import Context
from core.storage import get_backend


def generate(args, context: Context, config: Dict) -> Dict[str, Any]:
    """Generate GitHub job summary."""
    backend = get_backend(config['storage'], config)

    # Load workflow state
    workflow_name = args.workflow or context.workflow_name
    run_id = args.run_id or context.run_id
    
    # Try to load state for the specific workflow
    state = backend.get_state(f"workflow-{workflow_name}")
    
    # If no state found for specific workflow, try to find any state for this run
    if not state and run_id:
        all_states = backend.load_all_states()
        for key, s in all_states.items():
            if s.get('run_id') == run_id:
                state = s
                workflow_name = key.replace('workflow-', '')
                break
    
    # Build summary markdown
    if not state:
        # Workflow didn't run (likely due to dependency failure)
        summary = f"""## CI Workflow Summary: {workflow_name}

**Status:** ⏭️ SKIPPED

### Details
- **Workflow:** {workflow_name}
- **Run ID:** {run_id or 'N/A'}
- **Reason:** This workflow did not execute (likely due to dependency failure in a previous workflow)

"""
    else:
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

    # Parse artifacts if artifact directory is provided
    if args.artifact_dir:
        artifact_path = Path(args.artifact_dir)
        if artifact_path.exists():
            summary += parse_artifacts(artifact_path)

    # Add errors section if present (only if state exists)
    if state and state.get('errors'):
        summary += "### Errors\n"
        for error in state['errors']:
            summary += f"- {error.get('type', 'Unknown')}: {error.get('message', 'No message')}\n"
        summary += "\n"

    # Write to GitHub step summary
    if context.step_summary_path:
        summary_path = Path(context.step_summary_path)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_path, 'a') as f:
            f.write(summary)

    return {
        'status': 'generated',
        'workflow': workflow_name,
        'summary_path': context.step_summary_path
    }


def parse_artifacts(artifact_path: Path) -> str:
    """Parse artifacts and generate summary sections."""
    summary = ""
    
    # List all downloaded artifacts
    summary += "### Downloaded Artifacts\n"
    for f in artifact_path.rglob('*'):
        if f.is_file():
            summary += f"- {f.relative_to(artifact_path)}\n"
    summary += "\n"
    
    # Check for specific reports and display them
    summary += "### Test Results\n"
    junit_path = artifact_path / "pytest-reports" / "junit.xml"
    if junit_path.exists():
        summary += "✅ Pytest results found\n"
        summary += parse_junit_xml(junit_path)
    else:
        summary += "❌ No pytest results found\n"
    summary += "\n"
    
    # Lint results
    summary += "### Lint Results\n"
    mypy_path = artifact_path / "mypy-report" / "mypy.txt"
    if mypy_path.exists():
        summary += "✅ Mypy report found\n"
        summary += f"```text\n{mypy_path.read_text()[:2000]}\n```\n"
    else:
        summary += "❌ No mypy report found\n"
    
    ruff_path = artifact_path / "ruff-reports" / "ruff.txt"
    if ruff_path.exists():
        summary += "✅ Ruff report found\n"
        summary += f"```text\n{ruff_path.read_text()[:2000]}\n```\n"
    else:
        summary += "❌ No ruff report found\n"
    summary += "\n"
    
    # Security scan results
    summary += "### Security Scan Results\n"
    trivy_path = artifact_path / "trivy-results" / "trivy-results.sarif"
    if trivy_path.exists():
        summary += "✅ Trivy SARIF report found\n"
    else:
        summary += "❌ No Trivy report found\n"
    
    safety_path = artifact_path / "safety-report" / "safety-report.json"
    if safety_path.exists():
        summary += "✅ Safety report found\n"
    else:
        summary += "❌ No safety report found\n"
    summary += "\n"
    
    # Coverage results
    summary += "### Coverage Results\n"
    coverage_path = artifact_path / "code-coverage-report" / "coverage.xml"
    if coverage_path.exists():
        summary += "✅ Coverage report found\n"
    else:
        summary += "❌ No coverage report found\n"
    
    return summary


def parse_junit_xml(junit_path: Path) -> str:
    """Parse junit.xml and return formatted summary."""
    try:
        tree = ET.parse(junit_path)
        root = tree.getroot()
        tests = root.get('tests', '0')
        failures = root.get('failures', '0')
        errors = root.get('errors', '0')
        skipped = root.get('skipped', '0')
        time = root.get('time', '0')
        return f"- Total tests: {tests}\n- Failures: {failures}\n- Errors: {errors}\n- Skipped: {skipped}\n- Time: {time}s\n"
    except Exception as e:
        return f"- Could not parse junit.xml: {e}\n"


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
