"""Artifact management module."""
import json
import os
from pathlib import Path
from typing import Dict, Any, List
from core.context import Context
from core.storage import get_backend


def collect(args, context: Context, config: Dict) -> Dict[str, Any]:
    """Collect artifacts from various sources."""
    backend = get_backend(config['storage'], config)

    # Collect artifacts from common locations
    artifacts = []

    # Check for pytest results
    pytest_files = list(Path('.').glob('**/pytest-*.xml'))
    for file in pytest_files:
        try:
            with open(file, 'r') as f:
                artifacts.append({
                    'type': 'pytest',
                    'path': str(file),
                    'content': f.read()
                })
        except Exception:
            pass

    # Check for bandit results
    bandit_files = list(Path('.').glob('**/bandit-*.json'))
    for file in bandit_files:
        try:
            with open(file, 'r') as f:
                artifacts.append({
                    'type': 'bandit',
                    'path': str(file),
                    'content': json.load(f)
                })
        except Exception:
            pass

    # Check for coverage reports
    coverage_files = list(Path('.').glob('**/coverage.xml'))
    for file in coverage_files:
        try:
            with open(file, 'r') as f:
                artifacts.append({
                    'type': 'coverage',
                    'path': str(file),
                    'content': f.read()
                })
        except Exception:
            pass

    # Save artifacts to state
    workflow_name = context.workflow_name or 'unknown'
    backend.save_state(f"artifacts-{workflow_name}", {
        'workflow': workflow_name,
        'commit': context.commit_sha,
        'run_id': context.run_id,
        'artifacts': artifacts,
        'count': len(artifacts)
    })

    return {
        'status': 'collected',
        'workflow': workflow_name,
        'artifact_count': len(artifacts),
        'artifacts': [a['type'] for a in artifacts]
    }
