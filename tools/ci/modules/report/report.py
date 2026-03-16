"""Report aggregation module."""
import argparse
from typing import Dict, Any, List
from ...core.context import Context
from ...core.storage import get_backend


def aggregate(args: argparse.Namespace, context: Context, config: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregate all workflow results into final report."""
    backend = get_backend(config['storage'], config)

    # Load all workflow states
    all_states = backend.load_all_states()

    # Filter for current run
    run_id = args.run_id or context.run_id
    workflow_states = {}
    for key, state in all_states.items():
        if state.get('run_id') == run_id:
            workflow_states[key] = state

    # Build final report
    report: Dict[str, Any] = {
        'run_id': run_id,
        'commit': context.commit_sha,
        'repository': context.repository,
        'branch': context.run_url.split('/')[-2] if context.run_url else 'unknown',
        'workflows': {},
        'summary': {}
    }

    # Add workflow results
    for workflow_name, state in workflow_states.items():
        report['workflows'][workflow_name] = {
            'status': state.get('status', 'unknown'),
            'duration': state.get('duration', 0),
            'errors': state.get('errors', [])
        }

    # Calculate summary
    total_workflows = len(workflow_states)
    successful = sum(1 for s in workflow_states.values() if s.get('status') == 'success')
    failed = sum(1 for s in workflow_states.values() if s.get('status') == 'failure')

    report['summary'] = {
        'total_workflows': total_workflows,
        'successful': successful,
        'failed': failed,
        'success_rate': (successful / total_workflows * 100) if total_workflows > 0 else 0
    }

    # Save report
    backend.save_state(f"final-report-{run_id}", report)

    return report
