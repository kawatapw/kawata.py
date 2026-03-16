"""GitHub job summary generator."""
import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional, cast
from jinja2 import Environment, FileSystemLoader
from ...core.context import Context
from ...core.storage import get_backend
from ..parsers.registry import parse_file, detect_parser, list_parsers


def _find_state_in_artifacts(artifact_path: Path, workflow_name: str, run_id: str) -> Dict[str, Any]:
    """Find workflow state in downloaded artifacts.
    
    When artifacts are downloaded, they are stored in subdirectories named after the artifact.
    State files are stored in ci-data/state/workflow-*.json within those subdirectories.
    """
    print(f"DEBUG: Looking for state in artifacts at {artifact_path}")
    print(f"DEBUG: Looking for workflow_name={workflow_name}, run_id={run_id}")
    
    # Look for state files in all subdirectories
    for state_file in artifact_path.rglob('**/state/workflow-*.json'):
        print(f"DEBUG: Found state file: {state_file}")
        try:
            with open(state_file, 'r') as f:
                state = cast(Dict[str, Any], json.load(f))
                print(f"DEBUG: State file run_id={state.get('run_id')}, workflow={state_file.stem}")
                # Check if this state matches our workflow or run_id
                if state.get('run_id') == run_id:
                    print(f"DEBUG: Found matching state by run_id")
                    return state
                # Also check by workflow name
                state_workflow = state_file.stem.replace('workflow-', '')
                if state_workflow == workflow_name:
                    print(f"DEBUG: Found matching state by workflow name")
                    return state
        except Exception as e:
            print(f"DEBUG: Error reading state file {state_file}: {e}")
            continue
    
    # Also try to find any state file with matching run_id
    for state_file in artifact_path.rglob('**/state/*.json'):
        print(f"DEBUG: Found state file (any): {state_file}")
        try:
            with open(state_file, 'r') as f:
                state = cast(Dict[str, Any], json.load(f))
                if state.get('run_id') == run_id:
                    print(f"DEBUG: Found matching state by run_id (any)")
                    return state
        except Exception as e:
            print(f"DEBUG: Error reading state file {state_file}: {e}")
            continue
    
    print(f"DEBUG: No matching state found")
    return {}


def generate(args: argparse.Namespace, context: Context, config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate GitHub job summary using Jinja2 templates."""
    backend = get_backend(config['storage'], config)

    # Load workflow state
    workflow_name = args.workflow or context.workflow_name
    run_id = args.run_id or context.run_id
    
    print(f"DEBUG: generate() called with workflow_name={workflow_name}, run_id={run_id}")
    print(f"DEBUG: args.artifact_dir={getattr(args, 'artifact_dir', None)}")
    
    # Try to load state for the specific workflow
    state = backend.get_state(f"workflow-{workflow_name}")
    print(f"DEBUG: State from backend.get_state: {state is not None}")
    
    # If no state found for specific workflow, try to find any state for this run
    if not state and run_id:
        all_states = backend.load_all_states()
        print(f"DEBUG: Found {len(all_states)} states in backend")
        for key, s in all_states.items():
            if s.get('run_id') == run_id:
                state = s
                workflow_name = key.replace('workflow-', '')
                print(f"DEBUG: Found matching state by run_id: {key}")
                break
    
    # If still no state found and artifact_dir is provided, try to find state in artifacts
    if not state and args.artifact_dir:
        artifact_path = Path(args.artifact_dir)
        print(f"DEBUG: Looking for state in artifacts at {artifact_path}")
        if artifact_path.exists():
            state = _find_state_in_artifacts(artifact_path, workflow_name, run_id)
            print(f"DEBUG: State from artifacts: {state is not None}")
    
    # Prepare template data
    template_data: Dict[str, Any] = {
        'workflow_name': workflow_name,
        'run_id': run_id or 'N/A',
        'status': 'SKIPPED',
        'duration': 'N/A',
        'start_time': 'N/A',
        'completed_time': 'N/A',
        'commit': 'N/A',
        'test_results': '',
        'lint_results': '',
        'security_results': '',
        'coverage_results': '',
        'artifacts': [],
        'errors': []
    }
    
    if state:
        print(f"DEBUG: State found, updating template data")
        print(f"DEBUG: State status={state.get('status')}, duration={state.get('duration')}")
        template_data.update({
            'status': state['status'].upper(),
            'duration': format_duration(state.get('duration', 0)),
            'start_time': state.get('start_time', 'N/A'),
            'completed_time': state.get('completed_time', 'N/A'),
            'commit': state.get('commit', 'N/A'),
            'errors': state.get('errors', [])
        })
    else:
        print(f"DEBUG: No state found, using default template data")
    
    # Parse artifacts if artifact directory is provided
    if args.artifact_dir:
        artifact_path = Path(args.artifact_dir)
        print(f"DEBUG: Parsing artifacts from {artifact_path}")
        if artifact_path.exists():
            artifact_results = parse_artifacts_structured(artifact_path)
            template_data.update(artifact_results)
            print(f"DEBUG: Artifact results: test_results={len(artifact_results.get('test_results', ''))}, lint_results={len(artifact_results.get('lint_results', ''))}, security_results={len(artifact_results.get('security_results', ''))}")
        else:
            print(f"DEBUG: Artifact path does not exist: {artifact_path}")
    
    # Load and render template
    template_dir = Path(__file__).parent.parent.parent / 'templates'
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template('workflow_summary.md')
    
    summary = template.render(**template_data)
    
    # Write to GitHub step summary
    if context.step_summary_path:
        summary_path = Path(context.step_summary_path)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        # Use write mode to avoid duplicates when summary is generated multiple times
        with open(summary_path, 'w') as f:
            f.write(summary)

    return {
        'status': 'generated',
        'workflow': workflow_name,
        'summary_path': context.step_summary_path
    }


def parse_artifacts_structured(artifact_path: Path) -> Dict[str, Any]:
    """Parse artifacts and return structured data for template rendering."""
    result: Dict[str, Any] = {
        'test_results': '',
        'lint_results': '',
        'security_results': '',
        'coverage_results': '',
        'artifacts': []
    }
    
    # List all downloaded artifacts
    for f in artifact_path.rglob('*'):
        if f.is_file():
            result['artifacts'].append(str(f.relative_to(artifact_path)))
    
    # Debug: Print all found files
    print(f"DEBUG: Found {len(result['artifacts'])} files in {artifact_path}")
    for artifact in result['artifacts'][:10]:  # Limit to first 10
        print(f"DEBUG:   - {artifact}")
    
    # Define report categories and their associated parsers
    report_categories: Dict[str, Dict[str, Any]] = {
        'test_results': {
            'parsers': ['pytest'],
            'files': ['junit.xml', 'pytest.xml', 'test-results.xml'],
        },
        'lint_results': {
            'parsers': ['mypy', 'ruff'],
            'files': ['mypy.txt', 'mypy.log', 'ruff.txt', 'ruff.json'],
        },
        'security_results': {
            'parsers': ['bandit', 'trivy', 'safety'],
            'files': ['bandit.json', 'trivy-results.sarif', 'trivy.json', 'safety-report.json'],
        },
        'coverage_results': {
            'parsers': [],  # Coverage uses special handling
            'files': ['coverage.xml', 'coverage.json'],
        }
    }
    
    # Track which files have been processed
    processed_files = set()
    
    # Process each category
    for category, config in report_categories.items():
        config_dict: Dict[str, Any] = config
        category_content = ""
        found_reports = False
        
        # Find and parse matching files
        for f in artifact_path.rglob('*'):
            if not f.is_file() or f in processed_files:
                continue
            
            filename = f.name.lower()
            
            # Check if file matches any expected filenames
            matches_file = any(expected in filename for expected in config_dict['files'])
            
            # Check if file matches parser type in filename
            matches_parser = any(parser in filename for parser in config_dict['parsers'])
            
            if matches_file or matches_parser:
                try:
                    # Detect parser type
                    parser_type = detect_parser(str(f))
                    
                    # Debug: Print what we're parsing
                    print(f"DEBUG: Parsing {f.name} with parser {parser_type} for category {category}")
                    
                    # Parse the file
                    parsed = parse_file(str(f), parser_type)
                    
                    # Format the result
                    formatted = format_parser_result(parser_type, parsed)
                    if formatted:
                        category_content += formatted
                        found_reports = True
                        processed_files.add(f)
                        print(f"DEBUG: Successfully parsed {f.name}")
                    else:
                        print(f"DEBUG: No formatted output for {f.name}")
                except Exception as e:
                    category_content += f"⚠️ Error parsing {f.name}: {e}\n"
                    processed_files.add(f)
                    print(f"DEBUG: Error parsing {f.name}: {e}")
        
        # Add category content if reports were found
        if found_reports:
            result[category] = category_content
    
    return result


def parse_artifacts(artifact_path: Path) -> str:
    """Parse artifacts and generate summary sections using parser registry."""
    summary = ""
    
    # List all downloaded artifacts
    summary += "### Downloaded Artifacts\n"
    for f in artifact_path.rglob('*'):
        if f.is_file():
            summary += f"- {f.relative_to(artifact_path)}\n"
    summary += "\n"
    
    # Define report categories and their associated parsers
    report_categories: Dict[str, Dict[str, Any]] = {
        'Test Results': {
            'parsers': ['pytest'],
            'files': ['junit.xml', 'pytest.xml', 'test-results.xml'],
            'icon': '🧪'
        },
        'Lint Results': {
            'parsers': ['mypy', 'ruff'],
            'files': ['mypy.txt', 'mypy.log', 'ruff.txt', 'ruff.json'],
            'icon': '🔍'
        },
        'Security Scan Results': {
            'parsers': ['bandit', 'trivy', 'safety'],
            'files': ['bandit.json', 'trivy-results.sarif', 'trivy.json', 'safety-report.json'],
            'icon': '🔒'
        },
        'Coverage Results': {
            'parsers': [],  # Coverage uses special handling
            'files': ['coverage.xml', 'coverage.json'],
            'icon': '📊'
        }
    }
    
    # Track which files have been processed
    processed_files = set()
    
    # Process each category
    for category, config in report_categories.items():
        category_summary = ""
        found_reports = False
        
        # Find and parse matching files
        for f in artifact_path.rglob('*'):
            if not f.is_file() or f in processed_files:
                continue
            
            filename = f.name.lower()
            
            # Check if file matches any expected filenames
            matches_file = any(expected in filename for expected in config['files'])
            
            # Check if file matches parser type in filename
            matches_parser = any(parser in filename for parser in config['parsers'])
            
            if matches_file or matches_parser:
                try:
                    # Detect parser type
                    parser_type = detect_parser(str(f))
                    
                    # Parse the file
                    result = parse_file(str(f), parser_type)
                    
                    # Format the result
                    formatted = format_parser_result(parser_type, result)
                    if formatted:
                        category_summary += formatted
                        found_reports = True
                        processed_files.add(f)
                except Exception as e:
                    category_summary += f"⚠️ Error parsing {f.name}: {e}\n"
                    processed_files.add(f)
        
        # Add category section if reports were found
        if found_reports:
            summary += f"### {config['icon']} {category}\n"
            summary += category_summary
            summary += "\n"
    
    # Handle any remaining unprocessed files
    remaining_files = []
    for f in artifact_path.rglob('*'):
        if f.is_file() and f not in processed_files:
            remaining_files.append(f)
    
    if remaining_files:
        summary += "### 📁 Other Files\n"
        for f in remaining_files[:10]:  # Limit to first 10 files
            summary += f"- {f.relative_to(artifact_path)}\n"
        if len(remaining_files) > 10:
            summary += f"- ... and {len(remaining_files) - 10} more files\n"
        summary += "\n"
    
    return summary


def format_parser_result(parser_type: str, result: Dict[str, Any]) -> str:
    """Format parser result for summary display."""
    formatters = {
        'pytest': format_pytest_result,
        'mypy': format_mypy_result,
        'ruff': format_ruff_result,
        'bandit': format_bandit_result,
        'trivy': format_trivy_result,
        'safety': format_safety_result,
    }
    
    formatter = formatters.get(parser_type, format_generic_result)
    return formatter(result)


def format_pytest_result(result: Dict[str, Any]) -> str:
    """Format pytest result."""
    summary = result.get('summary', {})
    total = summary.get('total', 0)
    passed = summary.get('passed', 0)
    failed = summary.get('failed', 0)
    errors = summary.get('errors', 0)
    skipped = summary.get('skipped', 0)
    duration = summary.get('duration', 0)
    
    status_icon = '✅' if failed == 0 and errors == 0 else '❌'
    
    output = f"{status_icon} **Pytest Results**\n"
    output += f"- Total: {total} | Passed: {passed} | Failed: {failed} | Errors: {errors} | Skipped: {skipped}\n"
    output += f"- Duration: {duration:.2f}s\n"
    
    # Add failed test details if any
    if failed > 0 or errors > 0:
        test_cases = result.get('test_cases', [])
        failed_tests = [tc for tc in test_cases if tc.get('status') == 'failed']
        if failed_tests:
            output += "\n**Failed Tests:**\n"
            for tc in failed_tests[:5]:  # Limit to first 5
                output += f"- `{tc.get('classname', '')}.{tc.get('name', '')}`: {tc.get('message', '')[:100]}\n"
            if len(failed_tests) > 5:
                output += f"- ... and {len(failed_tests) - 5} more\n"
    
    return output + "\n"


def format_mypy_result(result: Dict[str, Any]) -> str:
    """Format mypy result."""
    summary = result.get('summary', {})
    total_errors = summary.get('total_errors', 0)
    total_warnings = summary.get('total_warnings', 0)
    total_notes = summary.get('total_notes', 0)
    files_with_errors = summary.get('files_with_errors', 0)
    
    status_icon = '✅' if total_errors == 0 else '❌'
    
    output = f"{status_icon} **Mypy Type Checking**\n"
    output += f"- Errors: {total_errors} | Warnings: {total_warnings} | Notes: {total_notes}\n"
    output += f"- Files with errors: {files_with_errors}\n"
    
    # Add error details if any
    if total_errors > 0:
        issues = result.get('issues', [])
        error_issues = [i for i in issues if i.get('severity') == 'error']
        if error_issues:
            output += "\n**Type Errors:**\n"
            for issue in error_issues[:5]:  # Limit to first 5
                output += f"- `{issue.get('file', '')}:{issue.get('line', '')}`: {issue.get('message', '')[:100]}\n"
            if len(error_issues) > 5:
                output += f"- ... and {len(error_issues) - 5} more\n"
    
    return output + "\n"


def format_ruff_result(result: Dict[str, Any]) -> str:
    """Format ruff result."""
    summary = result.get('summary', {})
    total_violations = summary.get('total_violations', 0)
    fixable = summary.get('fixable', 0)
    rules = summary.get('rules', {})
    
    status_icon = '✅' if total_violations == 0 else '⚠️'
    
    output = f"{status_icon} **Ruff Linting**\n"
    output += f"- Violations: {total_violations} | Fixable: {fixable}\n"
    
    # Add top rules
    if rules:
        top_rules = sorted(rules.items(), key=lambda x: x[1], reverse=True)[:5]
        output += "- Top rules: " + ", ".join(f"{rule} ({count})" for rule, count in top_rules) + "\n"
    
    # Add violation details if any
    if total_violations > 0:
        violations = result.get('violations', [])
        if violations:
            output += "\n**Violations:**\n"
            for v in violations[:5]:  # Limit to first 5
                output += f"- `{v.get('file', '')}:{v.get('line', '')}`: {v.get('rule_code', '')} - {v.get('message', '')[:80]}\n"
            if len(violations) > 5:
                output += f"- ... and {len(violations) - 5} more\n"
    
    return output + "\n"


def format_bandit_result(result: Dict[str, Any]) -> str:
    """Format bandit result."""
    summary = result.get('summary', {})
    total_issues = summary.get('total_issues', 0)
    high = summary.get('high_severity', 0)
    medium = summary.get('medium_severity', 0)
    low = summary.get('low_severity', 0)
    
    status_icon = '✅' if high == 0 else '❌'
    
    output = f"{status_icon} **Bandit Security Scan**\n"
    output += f"- Total issues: {total_issues} | High: {high} | Medium: {medium} | Low: {low}\n"
    
    # Add issue details if any
    if total_issues > 0:
        issues = result.get('issues', [])
        high_issues = [i for i in issues if i.get('severity') == 'HIGH']
        if high_issues:
            output += "\n**High Severity Issues:**\n"
            for issue in high_issues[:5]:  # Limit to first 5
                output += f"- `{issue.get('file_path', '')}:{issue.get('line_number', '')}`: {issue.get('test_name', '')} - {issue.get('issue_text', '')[:80]}\n"
            if len(high_issues) > 5:
                output += f"- ... and {len(high_issues) - 5} more\n"
    
    return output + "\n"


def format_trivy_result(result: Dict[str, Any]) -> str:
    """Format trivy result."""
    summary = result.get('summary', {})
    total = summary.get('total_vulnerabilities', 0)
    critical = summary.get('critical', 0)
    high = summary.get('high', 0)
    medium = summary.get('medium', 0)
    low = summary.get('low', 0)
    
    status_icon = '✅' if critical == 0 and high == 0 else '❌'
    
    output = f"{status_icon} **Trivy Vulnerability Scan**\n"
    output += f"- Total: {total} | Critical: {critical} | High: {high} | Medium: {medium} | Low: {low}\n"
    
    # Add vulnerability details if any
    if critical > 0 or high > 0:
        vulns = result.get('vulnerabilities', [])
        critical_vulns = [v for v in vulns if v.get('severity') in ('critical', 'high')]
        if critical_vulns:
            output += "\n**Critical/High Vulnerabilities:**\n"
            for v in critical_vulns[:5]:  # Limit to first 5
                pkg_info = f"{v.get('package', '')} ({v.get('installed_version', '')})"
                output += f"- {v.get('id', '')}: {pkg_info} - {v.get('title', '')[:80]}\n"
            if len(critical_vulns) > 5:
                output += f"- ... and {len(critical_vulns) - 5} more\n"
    
    return output + "\n"


def format_safety_result(result: Dict[str, Any]) -> str:
    """Format safety result."""
    summary = result.get('summary', {})
    total = summary.get('total_vulnerabilities', 0)
    critical = summary.get('critical', 0)
    high = summary.get('high', 0)
    medium = summary.get('medium', 0)
    low = summary.get('low', 0)
    packages_scanned = summary.get('packages_scanned', 0)
    
    status_icon = '✅' if critical == 0 and high == 0 else '❌'
    
    output = f"{status_icon} **Safety Dependency Scan**\n"
    output += f"- Packages scanned: {packages_scanned}\n"
    output += f"- Vulnerabilities: {total} | Critical: {critical} | High: {high} | Medium: {medium} | Low: {low}\n"
    
    # Add vulnerability details if any
    if critical > 0 or high > 0:
        vulns = result.get('vulnerabilities', [])
        critical_vulns = [v for v in vulns if v.get('severity') in ('critical', 'high')]
        if critical_vulns:
            output += "\n**Critical/High Vulnerabilities:**\n"
            for v in critical_vulns[:5]:  # Limit to first 5
                pkg_info = f"{v.get('package', '')} ({v.get('installed_version', '')})"
                output += f"- {v.get('id', '')}: {pkg_info} - {v.get('description', '')[:80]}\n"
            if len(critical_vulns) > 5:
                output += f"- ... and {len(critical_vulns) - 5} more\n"
    
    return output + "\n"


def format_generic_result(result: Dict[str, Any]) -> str:
    """Format generic result."""
    result_type = result.get('type', 'unknown')
    
    # Try to extract meaningful summary
    if 'summary' in result:
        summary = result['summary']
        output = f"**{result_type.title()} Results**\n"
        for key, value in summary.items():
            output += f"- {key.replace('_', ' ').title()}: {value}\n"
        return output + "\n"
    
    # For generic text, show line count
    if result.get('type') == 'generic_text':
        lines = result.get('lines', 0)
        return f"**Generic Report** ({lines} lines)\n\n"
    
    return ""


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
