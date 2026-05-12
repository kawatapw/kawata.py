# Logging Overhaul - Master Specification

## Overview

This document outlines a comprehensive overhaul of the logging system for the bancho.py project. The goal is to transform the current monolithic `app/logging.py` (880 lines) into a well-organized, reusable, and extensible logging package that can be shared across multiple projects.

## Goals

1. **Code Organization**: Split monolithic module into logical, focused submodules
2. **Separation of Concerns**: Colors for console only, clean structured logs for ELK
3. **Reusability**: Create a package that works across projects with minimal dependencies
4. **Request Tracing**: Implement correlation IDs for tracking requests across logs
5. **Developer Experience**: Easy to use, well-documented, with built-in test utilities
6. **Incremental Migration**: Smooth transition without breaking existing functionality

## Design Principles

- **Single Responsibility**: Each module/file has one clear purpose
- **Open/Plugin Architecture**: Core is extensible via plugins/adapters
- **Configuration via Dataclass**: Type-safe, IDE-friendly configuration
- **Comprehensive Documentation**: Google-style docstrings with examples
- **Two-Level API**: Simple functions for basic use, full access for advanced scenarios

## Package Structure

```
app/logging/
├── __init__.py          # Public API exports
├── config.py            # LoggingConfig dataclass
├── levels.py            # Custom log levels (VERBOSE, DBGLV2, DBGLV1)
├── ansi.py              # ANSI color codes
├── context.py           # Request context and correlation IDs
├── filters.py           # Debug filters and level filters
├── formatters.py        # Console, JSON, and structlog formatters
├── handlers.py          # Custom handlers
├── serializers.py       # JSON serialization utilities
├── logger.py            # Main log() function and builder
├── structlog_wrapper.py # Structlog integration wrapper
├── testing.py           # Test utilities and helpers
└── plugins/
    ├── __init__.py      # Plugin registration
    ├── request_formatters.py  # HTTP request formatters
    └── error_handler.py       # Error catcher decorator
```

## Key Features

### 1. Configuration (`config.py`)

```python
@dataclass
class LoggingConfig:
    """Configuration for the logging system.

    Attributes:
        service_name: Name of the service for log identification.
        container_name: Name of the container/instance.
        debug_level: Current debug verbosity level (0-3).
        debug_focus: Module/component to focus debug logs on.
        log_with_colors: Whether to use ANSI colors in console output.
        log_format: Output format ('console', 'json', 'structured').
        log_file: Optional file path for log output.
    """
    service_name: str = "osu_server"
    container_name: str = "bancho"
    debug_level: int = 0
    debug_focus: str = "all"
    log_with_colors: bool = True
    log_format: str = "console"
    log_file: str | None = None
```

### 2. Custom Log Levels (`levels.py`)

Keep the existing custom levels but implement them properly:

```python
class LogLevel(IntEnum):
    """Custom log levels for granular debug control.

    Standard Levels:
        DEBUG (10): Detailed diagnostic information
        INFO (20): General operational information
        WARNING (30): Potential issues
        ERROR (40): Error conditions
        CRITICAL (50): Critical errors

    Custom Debug Levels:
        VERBOSE (11): Extended diagnostic information
        DBGLV2 (14): Debug level 2 - detailed component logs
        DBGLV1 (16): Debug level 1 - focused component logs
    """
    DEBUG = 10
    VERBOSE = 11
    DBGLV2 = 14
    DBGLV1 = 16
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
```

### 3. Request Context & Correlation IDs (`context.py`)

```python
class RequestContext:
    """Holds context for the current request/operation.

    Attributes:
        request_id: Unique identifier for this request.
        correlation_id: ID that may be passed from external systems.
        player_id: Optional player ID for player-specific logs.
        start_time: When the request started.
    """

    def __init__(self, ...):
        ...

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for log inclusion."""
        ...


class LogContext:
    """Context manager for setting request context.

    Usage:
        with LogContext(request_id="abc123", player_id=12345):
            log.info("Processing score")  # Automatically includes context
    """
    ...
```

### 4. Formatters (`formatters.py`)

Separate formatters for different outputs:

- **ConsoleFormatter**: Adds ANSI colors, human-readable
- **JsonFormatter**: Clean JSON for ELK, no colors
- **StructlogFormatter**: Integration with structlog processors

```python
class ConsoleFormatter(logging.Formatter):
    """Formatter for console output with optional ANSI colors.

    Adds color based on log level when colors are enabled.
    Never includes color codes in the actual log message to keep
    structured logs clean.
    """
    ...


class JsonFormatter(logging.Formatter):
    """Formatter for JSON output to ELK/structured logging.

    Ensures all output is valid JSON with no ANSI escape codes.
    Includes timestamp, level, message, and any extra fields.
    """
    ...
```

### 5. Main Logger API (`logger.py`)

```python
# Simple API (backward compatible)
def log(
    msg: str,
    *,
    level: int = logging.INFO,
    color: Ansi | None = None,
    extra: dict[str, Any] | None = None,
    exc_info: bool = False,
) -> None:
    """Log a message with optional color and extra context.

    Args:
        msg: The message to log.
        level: Log level (use logging module constants or LogLevel).
        color: Optional ANSI color for console output.
        extra: Additional fields to include in structured logs.
        exc_info: Whether to include exception information.

    Examples:
        >>> log("Server started", color=Ansi.LGREEN)
        >>> log("Error occurred", level=logging.ERROR, exc_info=True)
        >>> log("Player action", extra={"player_id": 123, "action": "login"})
    """
    ...


# Builder pattern for complex logging
class LogBuilder:
    """Builder for complex log entries with multiple context fields.

    Usage:
        LogBuilder("Score submitted")
            .with_level(logging.INFO)
            .with_player(player)
            .with_extra({"score_id": score.id, "pp": score.pp})
            .with_request_id(request_id)
            .log()
    """
    ...


# Structlog wrapper
def get_logger(name: str) -> StructlogWrapper:
    """Get a structlog logger with our custom configuration.

    Provides a clean API that wraps structlog with our conventions.
    """
    ...


class StructlogWrapper:
    """Wrapper around structlog that provides a cleaner API.

    Usage:
        logger = get_logger("scores")
        logger.info("Score submitted", player_id=123, score_id=456)
        logger.error("Score validation failed", exc_info=True)
    """
    ...
```

### 6. Error Handler Plugin (`plugins/error_handler.py`)

```python
def error_catcher(
    func: Callable | None = None,
    *,
    logger: str | None = None,
    level: int = logging.ERROR,
    reraise: bool = True,
) -> Callable:
    """Decorator that catches and logs exceptions with full context.

    Can be used with or without arguments:
        @error_catcher
        async def my_func(): ...

        @error_catcher(logger="scores", reraise=False)
        async def my_func(): ...

    Args:
        func: The function to decorate (when used without parentheses).
        logger: Logger name to use (defaults to function's module).
        level: Log level for caught exceptions.
        reraise: Whether to re-raise the exception after logging.

    Returns:
        Decorated function that catches and logs exceptions.
    """
    ...
```

### 7. Request Formatter Plugin (`plugins/request_formatters.py`)

```python
class RequestFormatter(ABC):
    """Base class for HTTP request formatters.

    Subclass this to add support for different frameworks.
    """

    @abstractmethod
    def can_handle(self, request: Any) -> bool:
        """Check if this formatter can handle the given request."""
        ...

    @abstractmethod
    def format(self, request: Any) -> dict[str, Any]:
        """Format the request into a dictionary for logging."""
        ...


class FastAPIRequestFormatter(RequestFormatter):
    """Formatter for FastAPI Request objects."""
    ...


# Plugin registration
def register_formatter(formatter: RequestFormatter) -> None:
    """Register a request formatter for automatic request logging."""
    ...


def format_request(request: Any) -> dict[str, Any]:
    """Format a request using the appropriate registered formatter."""
    ...
```

### 8. Testing Utilities (`testing.py`)

```python
class LogCapture:
    """Context manager for capturing log output in tests.

    Usage:
        with LogCapture() as capture:
            log("Test message", level=logging.INFO)
            assert capture.has_message("Test message")
            assert capture.count_messages(level=logging.INFO) == 1
    """
    ...


@pytest.fixture
def log_capture():
    """Pytest fixture for log capture."""
    ...


def assert_log_contains(
    records: list[logging.LogRecord],
    message: str | None = None,
    level: int | None = None,
    **extra_fields: Any,
) -> bool:
    """Assert that log records contain a matching entry."""
    ...
```

## Migration Strategy

### Phase 1: Create New Package Structure
- Create `app/logging/` directory with all submodules
- Implement core functionality (config, levels, ansi, formatters)
- Add comprehensive tests for new code

### Phase 2: Implement New API
- Create new `log()` function with improved signature
- Implement `LogContext` for request tracking
- Create `LogBuilder` for complex logging scenarios
- Add structlog wrapper

### Phase 3: Backward Compatibility Layer
- Create compatibility module that maps old imports to new structure
- Add deprecation warnings for old usage patterns
- Ensure all existing code continues to work

### Phase 4: Gradual Migration
- Update imports in high-traffic areas first
- Migrate `error_catcher` usage
- Add request context to API endpoints
- Update background tasks

### Phase 5: Cleanup
- Remove old compatibility layer
- Update documentation
- Remove deprecated code

## Request ID Implementation

### Generation
- Auto-generate UUID v4 for each incoming HTTP request
- Accept external correlation ID from headers (`X-Correlation-ID`, `X-Request-ID`)
- Support passing correlation ID through async contexts

### Propagation
- Include in all log messages during request lifecycle
- Pass to downstream services via headers
- Store in structlog context vars for automatic inclusion

### Example Flow
```
Request → Middleware (generates/extracts ID) → Route Handler → Services
   ↓           ↓                                   ↓              ↓
Log Entry   Log Entry                           Log Entry     Log Entry
[req:abc]   [req:abc]                           [req:abc]     [req:abc]
```

## Documentation Standards

All public APIs must have Google-style docstrings with:
- Description
- Args section with types
- Returns section
- Raises section (if applicable)
- Examples section

```python
def example_function(param1: str, param2: int = 10) -> bool:
    """Short description of the function.

    Longer description if needed, explaining the function's purpose
    and any important details.

    Args:
        param1: Description of param1.
        param2: Description of param2. Defaults to 10.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param1 is empty.

    Examples:
        >>> example_function("test")
        True
        >>> example_function("test", param2=20)
        True
    """
    ...
```

## Success Criteria

- [ ] All existing tests pass without modification
- [ ] New package has >90% test coverage
- [ ] All public APIs have comprehensive docstrings
- [ ] Request IDs are included in all API request logs
- [ ] Console output has colors, JSON/ELK output is clean
- [ ] Package can be copied to frontend project with minimal changes
- [ ] Migration can be done incrementally without breaking changes
