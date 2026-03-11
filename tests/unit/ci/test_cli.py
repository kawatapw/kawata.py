"""Unit tests for CLI module."""
import sys
from pathlib import Path

# Add tools/ci to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / 'tools' / 'ci'))

from core.cli import parse_args


def test_parse_args_workflow_start():
    """Test parsing workflow start command."""
    # Simulate command line arguments
    sys.argv = ['ci.py', 'workflow', 'start', '--workflow', 'test']
    args = parse_args()

    assert args.module == 'workflow'
    assert args.action == 'start'
    assert args.workflow == 'test'


def test_parse_args_workflow_finish():
    """Test parsing workflow finish command."""
    sys.argv = ['ci.py', 'workflow', 'finish', '--workflow', 'test', '--status', 'success']
    args = parse_args()

    assert args.module == 'workflow'
    assert args.action == 'finish'
    assert args.workflow == 'test'
    assert args.status == 'success'


def test_parse_args_summary_generate():
    """Test parsing summary generate command."""
    sys.argv = ['ci.py', 'summary', 'generate', '--workflow', 'test']
    args = parse_args()

    assert args.module == 'summary'
    assert args.action == 'generate'
    assert args.workflow == 'test'


def test_parse_args_report_aggregate():
    """Test parsing report aggregate command."""
    sys.argv = ['ci.py', 'report', 'aggregate']
    args = parse_args()

    assert args.module == 'report'
    assert args.action == 'aggregate'


def test_parse_args_artifacts_collect():
    """Test parsing artifacts collect command."""
    sys.argv = ['ci.py', 'artifacts', 'collect']
    args = parse_args()

    assert args.module == 'artifacts'
    assert args.action == 'collect'


def test_parse_args_global_flags():
    """Test parsing global flags."""
    sys.argv = ['ci.py', '--verbose', '--debug', '--json', 'workflow', 'start']
    args = parse_args()

    assert args.verbose is True
    assert args.debug is True
    assert args.json is True
    assert args.module == 'workflow'
    assert args.action == 'start'
