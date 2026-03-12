"""Workflow lifecycle management."""
from datetime import datetime
from typing import Dict, Any

from core.context import Context
from core.storage import get_backend


def _workflow_key(workflow_name: str) -> str:
    return f"workflow-{workflow_name}"


def start(args, context: Context, config: Dict) -> Dict[str, Any]:
    """Start workflow or job tracking.

    Behaviour:
    - Without ``--job``: (workflow-level)
      - Ensure a workflow state exists and mark it as running.
    - With ``--job``: (job-level)
      - Ensure workflow state exists and start/update a job entry inside ``state['jobs']``.
    """
    backend = get_backend(config['storage'], config)

    workflow_name = args.workflow or context.workflow_name
    if not workflow_name:
        raise ValueError("Workflow name is required (via --workflow or GITHUB_WORKFLOW)")

    key = _workflow_key(workflow_name)
    state = backend.get_state(key) or {}

    # Initialize base workflow state if it doesn't exist yet
    if not state:
        state = {
            'workflow': workflow_name,
            'status': 'running',
            'start_time': datetime.utcnow().isoformat(),
            'commit': context.commit_sha,
            'run_id': context.run_id,
            'run_url': context.run_url,
            'jobs': [],
            'reports': [],
            'errors': [],
        }
    else:
        # Keep existing timing where possible but refresh contextual metadata
        state.setdefault('workflow', workflow_name)
        state.setdefault('start_time', datetime.utcnow().isoformat())
        state.setdefault('jobs', [])
        state.setdefault('reports', [])
        state.setdefault('errors', [])
        state['status'] = 'running'
        state['commit'] = context.commit_sha
        state['run_id'] = context.run_id
        state['run_url'] = context.run_url

    # Job-scoped start
    job_name = getattr(args, "job", None) or None
    if job_name:
        jobs = state.setdefault('jobs', [])
        now = datetime.utcnow().isoformat()

        # Find existing job entry if any
        job_entry = next((j for j in jobs if j.get('job') == job_name), None)
        job_state = {
            'job': job_name,
            'status': 'running',
            'start_time': now,
            'completed_time': None,
            'duration': None,
        }

        if job_entry is not None:
            job_entry.update(job_state)
        else:
            jobs.append(job_state)

        backend.save_state(key, state)
        return {
            'status': 'job-started',
            'workflow': workflow_name,
            'job': job_name,
            'run_id': context.run_id,
        }

    # Workflow-level start
    backend.save_state(key, state)
    return {
        'status': 'started',
        'workflow': workflow_name,
        'run_id': context.run_id,
    }


def finish(args, context: Context, config: Dict) -> Dict[str, Any]:
    """Finish workflow or job tracking.

    Behaviour:
    - With ``--job``: update the matching job entry inside ``state['jobs']`` and
      record per-job duration, but do *not* emit a separate workflow result.
    - Without ``--job``: treat as workflow-level finish, computing overall
      workflow duration and emitting a single workflow result.
    """
    backend = get_backend(config['storage'], config)

    workflow_name = args.workflow or context.workflow_name
    if not workflow_name:
        raise ValueError("Workflow name is required (via --workflow or GITHUB_WORKFLOW)")

    key = _workflow_key(workflow_name)
    state = backend.get_state(key)

    if not state:
        raise ValueError(f"No state found for workflow: {workflow_name}")

    job_name = getattr(args, "job", None) or None

    # Job-scoped finish
    if job_name:
        jobs = state.setdefault('jobs', [])
        now_iso = datetime.utcnow().isoformat()

        job_entry = next((j for j in jobs if j.get('job') == job_name), None)
        if job_entry is None:
            # Gracefully create a minimal job entry if start was never called
            job_entry = {
                'job': job_name,
                'start_time': now_iso,
                'status': 'running',
                'completed_time': None,
                'duration': None,
            }
            jobs.append(job_entry)

        job_entry['status'] = args.status or 'success'
        job_entry['completed_time'] = now_iso

        # Compute per-job duration if we have a start time
        try:
            if job_entry.get('start_time'):
                start_time = datetime.fromisoformat(job_entry['start_time'])
                end_time = datetime.fromisoformat(job_entry['completed_time'])
                job_entry['duration'] = (end_time - start_time).total_seconds()
        except Exception:
            # Leave duration unset rather than failing the workflow
            job_entry['duration'] = None

        # Optionally keep workflow-level start_time in sync with earliest job
        if not state.get('start_time'):
            job_starts = [j.get('start_time') for j in jobs if j.get('start_time')]
            if job_starts:
                state['start_time'] = min(job_starts)

        backend.save_state(key, state)
        return {
            'status': 'job-finished',
            'workflow': workflow_name,
            'job': job_name,
            'result_status': job_entry['status'],
        }

    # Workflow-level finish
    state['status'] = args.status or 'success'
    state['completed_time'] = datetime.utcnow().isoformat()

    # Calculate duration from workflow start/end
    start_time = datetime.fromisoformat(state['start_time'])
    end_time = datetime.fromisoformat(state['completed_time'])
    state['duration'] = (end_time - start_time).total_seconds()

    backend.save_state(key, state)

    # Save workflow result (one per workflow)
    result = {
        'commit': state['commit'],
        'workflow': workflow_name,
        'job': context.job_name,
        'status': state['status'],
        'started_at': state['start_time'],
        'completed_at': state['completed_time'],
        'duration': state['duration'],
        'run_id': state['run_id'],
        'run_url': state['run_url'],
    }
    backend.save_workflow_result(result)

    return {
        'status': 'finished',
        'workflow': workflow_name,
        'result_status': state['status'],
    }
