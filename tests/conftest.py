import pytest
import structlog
import logging

@pytest.fixture(autouse=True, scope='session')
def configure_test_logging():
    """Configure structlog and logging for tests."""
    # 1. Configure structlog to use standard library logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.render_to_log_kwargs,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 2. Setup a basic console handler so logs don't go to /dev/null
    # (Optional, but helpful for debugging tests)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    
    # Get the 'console' logger used by your log function
    console_logger = logging.getLogger('console')
    console_logger.setLevel(logging.DEBUG)
    console_logger.addHandler(handler)
    
    # Ensure the root logger is also set up
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)

    yield
    
    # Cleanup if necessary