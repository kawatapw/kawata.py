# Logging Overhaul - Implementation Plan

## Overview

This document provides step-by-step instructions for implementing the logging overhaul. Each section represents a discrete task that can be completed and tested independently.

---

## Step 1: Create Package Structure

### 1.1 Create Directory Structure

Create the following directory structure:

```
app/logging/
├── __init__.py
├── config.py
├── levels.py
├── ansi.py
├── context.py
├── filters.py
├── formatters.py
├── handlers.py
├── serializers.py
├── logger.py
├── structlog_wrapper.py
├── testing.py
└── plugins/
    ├── __init__.py
    ├── request_formatters.py
    └── error_handler.py
```

### 1.2 Create Empty Files with Module Docstrings

Each file should start with a module-level docstring:

```python
"""
Module description.

This module provides [specific functionality] for the logging system.
It handles [specific responsibility].

Typical usage example:
    from app.logging.module_name import SomeClass
    result = SomeClass().do_something()
"""
```

---

## Step 2: Implement Core Modules

### 2.1 `config.py` - Configuration Dataclass

```python
"""
Configuration dataclass for the logging system.

This module defines the LoggingConfig dataclass that holds all configuration
for the logging system. It can be populated from environment variables,
settings modules, or any other source.

Typical usage example:
    from app.logging.config import LoggingConfig
    
    config = LoggingConfig.from_settings(app.settings)
    # or
    config = LoggingConfig(service_name="my_service", debug_level=2)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LoggingConfig:
    """Configuration for the logging system.
    
    All configuration options for the logging system are defined here.
    This dataclass can be populated from any source (env vars, settings, etc.).
    
    Attributes:
        service_name: Name of the service for log identification.
            Used in structured logs to identify which service generated the log.
        container_name: Name of the container/instance.
            Useful for distinguishing between multiple instances of the same service.
        debug_level: Current debug verbosity level (0-3).
            0 = INFO only, 1 = DBGLV1, 2 = DBGLV2, 3 = VERBOSE
        debug_focus: Module/component to focus debug logs on.
            Only log messages with matching focus will be shown at debug levels.
        log_with_colors: Whether to use ANSI colors in console output.
            Should be False when outputting to files or structured logging systems.
        log_format: Output format type.
            'console' = human-readable with optional colors
            'json' = JSON format for ELK/structured logging
            'structured' = structlog format
        log_file: Optional file path for log output.
            If None, logs only go to console.
    
    Examples:
        >>> config = LoggingConfig()
        >>> config.service_name
        'osu_server'
        
        >>> config = LoggingConfig(service_name="frontend", debug_level=2)
        >>> config.debug_level
        2
    """
    
    service_name: str = "osu_server"
    container_name: str = "bancho"
    debug_level: int = 0
    debug_focus: str = "all"
    log_with_colors: bool = True
    log_format: str = "console"
    log_file: str | None = None
    
    @classmethod
    def from_settings(cls, settings: Any) -> LoggingConfig:
        """Create LoggingConfig from a settings module.
        
        Args:
            settings: Module or object with logging-related attributes.
                Expected attributes: SERVICE_NAME, CONTAINER_NAME, DEBUG_LEVEL,
                DEBUG_FOCUS, LOG_WITH_COLORS
        
        Returns:
            LoggingConfig populated from settings.
        
        Examples:
            >>> from app import settings
            >>> config = LoggingConfig.from_settings(settings)
        """
        return cls(
            service_name=getattr(settings, "SERVICE_NAME", "osu_server"),
            container_name=getattr(settings, "CONTAINER_NAME", "bancho"),
            debug_level=getattr(settings, "DEBUG_LEVEL", 0),
            debug_focus=getattr(settings, "DEBUG_FOCUS", "all"),
            log_with_colors=getattr(settings, "LOG_WITH_COLORS", True),
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary.
        
        Returns:
            Dictionary representation of the configuration.
        """
        return {
            "service_name": self.service_name,
            "container_name": self.container_name,
            "debug_level": self.debug_level,
            "debug_focus": self.debug_focus,
            "log_with_colors": self.log_with_colors,
            "log_format": self.log_format,
            "log_file": self.log_file,
        }
```

### 2.2 `levels.py` - Custom Log Levels

```python
"""
Custom log levels for granular debug control.

This module defines custom log levels that extend Python's standard logging
levels to provide more granular control over debug output. The custom levels
are registered with both Python's logging module and structlog.

Custom Levels:
    VERBOSE (11): Extended diagnostic information
    DBGLV2 (14): Debug level 2 - detailed component logs
    DBGLV1 (16): Debug level 1 - focused component logs

Typical usage example:
    from app.logging.levels import LogLevel, register_custom_levels
    
    register_custom_levels()
    logger.log(LogLevel.VERBOSE, "Detailed debug info")
"""

from __future__ import annotations

import logging
from enum import IntEnum
from typing import Any

import structlog


class LogLevel(IntEnum):
    """Custom log levels extending standard Python log levels.
    
    These levels provide more granular control over debug output,
    allowing developers to focus on specific components or verbosity levels.
    
    Standard Levels (from logging module):
        DEBUG (10): Detailed diagnostic information
        INFO (20): General operational information
        WARNING (30): Potential issues or important notices
        ERROR (40): Error conditions that need attention
        CRITICAL (50): Critical errors that may cause shutdown
    
    Custom Debug Levels:
        VERBOSE (11): Extended diagnostic information, most verbose
        DBGLV2 (14): Debug level 2 - detailed component logs
        DBGLV1 (16): Debug level 1 - focused component logs (least verbose)
    
    Examples:
        >>> LogLevel.VERBOSE
        <LogLevel.VERBOSE: 11>
        >>> LogLevel.VERBOSE.value
        11
        >>> LogLevel(11)
        <LogLevel.VERBOSE: 11>
    """
    
    DEBUG = 10
    VERBOSE = 11
    DBGLV2 = 14
    DBGLV1 = 16
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    
    @classmethod
    def get_name(cls, level: int) -> str:
        """Get the name for a log level value.
        
        Args:
            level: Integer log level value.
        
        Returns:
            String name of the log level, or "UNKNOWN" if not found.
        
        Examples:
            >>> LogLevel.get_name(11)
            'VERBOSE'
            >>> LogLevel.get_name(99)
            'UNKNOWN'
        """
        try:
            return cls(level).name
        except ValueError:
            return "UNKNOWN"


# Level name mappings for structlog integration
LEVEL_NAME_MAP: dict[str, int] = {
    "verbose": LogLevel.VERBOSE,
    "dbglv2": LogLevel.DBGLV2,
    "dbglv1": LogLevel.DBGLV1,
}


def register_custom_levels() -> None:
    """Register custom log levels with Python logging and structlog.
    
    This function must be called once during application startup to register
    the custom log levels with both Python's logging module and structlog.
    
    After calling this function, you can use the custom levels:
        logger.log(LogLevel.VERBOSE, "message")
        logger.log(11, "message")  # equivalent
    
    Examples:
        >>> register_custom_levels()
        >>> import logging
        >>> logging.getLevelName(11)
        'VERBOSE'
    """
    # Register with Python's logging module
    logging.addLevelName(LogLevel.VERBOSE, "VERBOSE")
    logging.addLevelName(LogLevel.DBGLV2, "DBGLV2")
    logging.addLevelName(LogLevel.DBGLV1, "DBGLV1")
    
    # Register with structlog
    name_to_level = getattr(structlog.stdlib, "NAME_TO_LEVEL", {})
    for name, level in LEVEL_NAME_MAP.items():
        name_to_level[name] = level


def get_level_for_debug_level(debug_level: int) -> int:
    """Convert debug level setting to log level.
    
    Args:
        debug_level: Debug level setting (0-3).
            0 = INFO, 1 = DBGLV1, 2 = DBGLV2, 3 = VERBOSE
    
    Returns:
        Corresponding log level integer.
    
    Examples:
        >>> get_level_for_debug_level(0)
        20
        >>> get_level_for_debug_level(3)
        11
    """
    level_map = {
        0: LogLevel.INFO,
        1: LogLevel.DBGLV1,
        2: LogLevel.DBGLV2,
        3: LogLevel.VERBOSE,
    }
    return level_map.get(debug_level, LogLevel.DEBUG)
```

### 2.3 `ansi.py` - ANSI Color Codes

```python
"""
ANSI escape codes for colored console output.

This module defines ANSI escape codes for coloring console output.
These colors should only be used for console output and should never
be included in structured logs (JSON, ELK, etc.).

The color codes follow standard ANSI escape sequences:
    \\x1b[<code>m

Where <code> is one of the color values defined in the Ansi enum.

Typical usage example:
    from app.logging.ansi import Ansi, colorize
    
    print(f"{Ansi.LGREEN}Success!{Ansi.RESET}")
    # or
    colored = colorize("Error!", Ansi.LRED)
"""

from __future__ import annotations

from enum import IntEnum


class Ansi(IntEnum):
    """ANSI escape codes for colored console output.
    
    These color codes can be used to add color to console output.
    They should NOT be included in structured logs or log files.
    
    Usage:
        print(f"{Ansi.LGREEN}Success!{Ansi.RESET}")
    
    Attributes:
        BLACK: Black text (30)
        RED: Red text (31)
        GREEN: Green text (32)
        YELLOW: Yellow text (33)
        BLUE: Blue text (34)
        MAGENTA: Magenta text (35)
        CYAN: Cyan text (36)
        WHITE: White text (37)
        GRAY: Gray text (90)
        LRED: Light red text (91)
        LGREEN: Light green text (92)
        LYELLOW: Light yellow text (93)
        LBLUE: Light blue text (94)
        LMAGENTA: Light magenta text (95)
        LCYAN: Light cyan text (96)
        LWHITE: Light white text (97)
        RESET: Reset all formatting (0)
    
    Examples:
        >>> Ansi.LGREEN
        <Ansi.LGREEN: 92>
        >>> repr(Ansi.LGREEN)
        '\\x1b[92m'
    """
    
    # Default colours
    BLACK = 30
    RED = 31
    GREEN = 32
    YELLOW = 33
    BLUE = 34
    MAGENTA = 35
    CYAN = 36
    WHITE = 37
    
    # Light colours
    GRAY = 90
    LRED = 91
    LGREEN = 92
    LYELLOW = 93
    LBLUE = 94
    LMAGENTA = 95
    LCYAN = 96
    LWHITE = 97
    
    RESET = 0
    
    def __repr__(self) -> str:
        """Return the ANSI escape sequence for this color.
        
        Returns:
            ANSI escape sequence string.
        """
        return f"\x1b[{self.value}m"


# Regex pattern for matching ANSI escape sequences
ANSI_ESCAPE_PATTERN = r"(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]"


def colorize(text: str, color: Ansi) -> str:
    """Wrap text with ANSI color codes.
    
    Args:
        text: The text to colorize.
        color: The ANSI color to apply.
    
    Returns:
        Text wrapped with color codes and reset.
    
    Examples:
        >>> colorize("Success!", Ansi.LGREEN)
        '\\x1b[92mSuccess!\\x1b[0m'
    """
    return f"{color!r}{text}{Ansi.RESET!r}"


def escape_ansi(line: str) -> str:
    """Remove ANSI escape sequences from a string.
    
    This is useful for cleaning log messages before sending to
    structured logging systems that don't support ANSI codes.
    
    Args:
        line: String that may contain ANSI escape sequences.
    
    Returns:
        String with all ANSI escape sequences removed.
    
    Examples:
        >>> escape_ansi("\\x1b[92mSuccess!\\x1b[0m")
        'Success!'
    """
    import re
    return re.sub(ANSI_ESCAPE_PATTERN, "", line)


def get_level_color(level: int) -> Ansi:
    """Get the appropriate color for a log level.
    
    Args:
        level: Log level integer.
    
    Returns:
        ANSI color code for the level.
    
    Examples:
        >>> get_level_color(20)  # INFO
        <Ansi.LCYAN: 96>
        >>> get_level_color(40)  # ERROR
        <Ansi.LRED: 91>
    """
    import logging
    
    if level <= logging.DEBUG:
        return Ansi.GRAY
    elif level <= 19:  # VERBOSE, DBGLV2, DBGLV1
        return Ansi.LBLUE
    elif level <= logging.INFO:
        return Ansi.LCYAN
    elif level <= logging.WARNING:
        return Ansi.LYELLOW
    elif level <= logging.ERROR:
        return Ansi.LRED
    else:
        return Ansi.RED
```

### 2.4 `context.py` - Request Context and Correlation IDs

```python
"""
Request context and correlation ID management.

This module provides functionality for tracking request context across
async boundaries, enabling correlation of logs from the same request.

The context is stored in contextvars, making it safe for use with asyncio.

Typical usage example:
    from app.logging.context import LogContext, get_request_id
    
    with LogContext(request_id="abc123", player_id=456):
        process_request()
        # All logs within this block will include request_id and player_id
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

# Context variables for storing request context
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_player_id: ContextVar[int | None] = ContextVar("player_id", default=None)
_extra_context: ContextVar[dict[str, Any]] = ContextVar("extra_context", default={})


@dataclass
class RequestContext:
    """Holds context information for the current request/operation.
    
    This context is automatically included in all log messages made
    during the request's lifetime.
    
    Attributes:
        request_id: Unique identifier for this request.
        correlation_id: External correlation ID (from load balancer, etc.).
        player_id: Optional player ID for player-specific operations.
        extra: Additional context fields to include in logs.
    
    Examples:
        >>> ctx = RequestContext(request_id="abc123", player_id=456)
        >>> ctx.to_dict()
        {'request_id': 'abc123', 'player_id': 456}
    """
    
    request_id: str | None = None
    correlation_id: str | None = None
    player_id: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for log inclusion.
        
        Returns:
            Dictionary with non-None context fields.
        """
        result = {}
        if self.request_id:
            result["request_id"] = self.request_id
        if self.correlation_id:
            result["correlation_id"] = self.correlation_id
        if self.player_id:
            result["player_id"] = self.player_id
        result.update(self.extra)
        return result
    
    def set(self) -> None:
        """Set this context as the current context.
        
        Examples:
            >>> ctx = RequestContext(request_id="abc123")
            >>> ctx.set()
            >>> get_request_id()
            'abc123'
        """
        if self.request_id:
            _request_id.set(self.request_id)
        if self.correlation_id:
            _correlation_id.set(self.correlation_id)
        if self.player_id:
            _player_id.set(self.player_id)
        if self.extra:
            _extra_context.set(self.extra)
    
    def clear(self) -> None:
        """Clear the current context.
        
        Examples:
            >>> clear_context()
            >>> get_request_id() is None
            True
        """
        _request_id.set(None)
        _correlation_id.set(None)
        _player_id.set(None)
        _extra_context.set({})


class LogContext:
    """Context manager for setting request context.
    
    Usage:
        with LogContext(request_id="abc123", player_id=456):
            # All logs here include the context
            log.info("Processing request")
    
    Can also be used as a decorator:
        @LogContext(player_id=456)
        def process_player():
            ...
    
    Examples:
        >>> with LogContext(request_id="test") as ctx:
        ...     assert get_request_id() == "test"
        >>> assert get_request_id() is None
    """
    
    def __init__(
        self,
        request_id: str | None = None,
        correlation_id: str | None = None,
        player_id: int | None = None,
        **extra: Any,
    ) -> None:
        """Initialize the log context.
        
        Args:
            request_id: Unique request ID. Generated if not provided.
            correlation_id: External correlation ID.
            player_id: Player ID for player-specific operations.
            **extra: Additional context fields.
        """
        self.request_id = request_id or generate_request_id()
        self.correlation_id = correlation_id
        self.player_id = player_id
        self.extra = extra
        self._token: Any = None
    
    def __enter__(self) -> LogContext:
        """Enter the context.
        
        Returns:
            Self for use as 'as' variable.
        """
        self._previous_context = get_current_context()
        RequestContext(
            request_id=self.request_id,
            correlation_id=self.correlation_id,
            player_id=self.player_id,
            extra=self.extra,
        ).set()
        return self
    
    def __exit__(self, *args: Any) -> None:
        """Exit the context, restoring previous context."""
        self._previous_context.set()
    
    def __call__(self, func: Any) -> Any:
        """Use as a decorator.
        
        Args:
            func: Function to decorate.
        
        Returns:
            Decorated function.
        """
        import functools
        
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with self:
                return func(*args, **kwargs)
        
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with self:
                return await func(*args, **kwargs)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper


def generate_request_id() -> str:
    """Generate a unique request ID.
    
    Returns:
        UUID v4 string.
    
    Examples:
        >>> rid = generate_request_id()
        >>> len(rid) == 36  # UUID v4 length
        True
    """
    return str(uuid.uuid4())


def get_request_id() -> str | None:
    """Get the current request ID.
    
    Returns:
        Current request ID or None if not set.
    """
    return _request_id.get()


def get_correlation_id() -> str | None:
    """Get the current correlation ID.
    
    Returns:
        Current correlation ID or None if not set.
    """
    return _correlation_id.get()


def get_player_id() -> int | None:
    """Get the current player ID.
    
    Returns:
        Current player ID or None if not set.
    """
    return _player_id.get()


def get_current_context() -> RequestContext:
    """Get the current request context.
    
    Returns:
        Current RequestContext.
    """
    return RequestContext(
        request_id=_request_id.get(),
        correlation_id=_correlation_id.get(),
        player_id=_player_id.get(),
        extra=_extra_context.get(),
    )


def clear_context() -> None:
    """Clear all context variables.
    
    Examples:
        >>> clear_context()
        >>> get_request_id() is None
        True
    """
    RequestContext().clear()


def get_context_dict() -> dict[str, Any]:
    """Get current context as dictionary for log inclusion.
    
    Returns:
        Dictionary with current context fields.
    """
    return get_current_context().to_dict()
```

---

## Step 3: Implement Formatters

### 3.1 `formatters.py` - Log Formatters

```python
"""
Log formatters for different output formats.

This module provides formatters for:
- Console output (human-readable, optional colors)
- JSON output (for ELK/structured logging)
- Structlog integration

The key principle is that colors are ONLY added by the console formatter
and never appear in structured/JSON output.

Typical usage example:
    from app.logging.formatters import ConsoleFormatter, JsonFormatter
    
    console_fmt = ConsoleFormatter(use_colors=True)
    json_fmt = JsonFormatter()
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any

from app.logging.ansi import Ansi, escape_ansi, get_level_color
from app.logging.context import get_context_dict


class ConsoleFormatter(logging.Formatter):
    """Formatter for console output with optional ANSI colors.
    
    This formatter produces human-readable output for console display.
    When colors are enabled, it adds ANSI escape codes based on log level.
    
    The format is:
        [TIMESTAMP] LEVEL Message
    
    With colors, the LEVEL portion is colored.
    
    Attributes:
        use_colors: Whether to add ANSI color codes.
        date_format: strftime format for timestamps.
    
    Examples:
        >>> fmt = ConsoleFormatter(use_colors=False)
        >>> fmt.format(logging.LogRecord("test", 20, "", 0, "msg", (), None))
        '[2024-01-01 12:00:00] INFO msg'
    """
    
    def __init__(
        self,
        use_colors: bool = True,
        date_format: str = "%Y-%m-%d %H:%M:%S",
    ) -> None:
        """Initialize the console formatter.
        
        Args:
            use_colors: Whether to add ANSI color codes.
            date_format: strftime format for timestamps.
        """
        super().__init__()
        self.use_colors = use_colors
        self.date_format = date_format
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record for console output.
        
        Args:
            record: The log record to format.
        
        Returns:
            Formatted log string.
        """
        timestamp = datetime.fromtimestamp(record.created).strftime(self.date_format)
        level_name = record.levelname
        message = record.getMessage()
        
        # Add context if available
        context = get_context_dict()
        context_str = ""
        if context:
            context_parts = [f"{k}={v}" for k, v in context.items()]
            context_str = f" [{', '.join(context_parts)}]"
        
        if self.use_colors:
            color = get_level_color(record.levelno)
            level_str = f"{color!r}{level_name:<8}{Ansi.RESET!r}"
        else:
            level_str = f"{level_name:<8}"
        
        return f"[{timestamp}] {level_str} {message}{context_str}"


class JsonFormatter(logging.Formatter):
    """Formatter for JSON output to ELK/structured logging.
    
    This formatter produces clean JSON output suitable for ingestion
    by Elasticsearch, Logstash, or other structured logging systems.
    
    It NEVER includes ANSI color codes.
    
    The output format is:
        {
            "timestamp": "2024-01-01T12:00:00",
            "level": "INFO",
            "logger": "module.name",
            "message": "Log message",
            "request_id": "abc123",
            ...
        }
    
    Examples:
        >>> fmt = JsonFormatter()
        >>> output = fmt.format(record)
        >>> parsed = json.loads(output)
        >>> parsed["level"]
        'INFO'
    """
    
    def __init__(self, service_name: str = "osu_server") -> None:
        """Initialize the JSON formatter.
        
        Args:
            service_name: Service name to include in all logs.
        """
        super().__init__()
        self.service_name = service_name
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON.
        
        Args:
            record: The log record to format.
        
        Returns:
            JSON string representation of the log entry.
        """
        # Build the base log entry
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": escape_ansi(record.getMessage()),
            "service.name": self.service_name,
        }
        
        # Add exception info if present
        if record.exc_info and record.exc_info[1]:
            log_entry["error"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }
        
        # Add context
        context = get_context_dict()
        log_entry.update(context)
        
        # Add extra fields from record
        standard_attrs = {
            "name", "msg", "args", "created", "relativeCreated", "exc_info",
            "exc_text", "lineno", "msecs", "pathname", "process", "processName",
            "stack_info", "thread", "threadName", "funcName", "levelno", "levelname",
            "message", "module",
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_entry[key] = value
        
        return json.dumps(log_entry, default=str)


class StructlogFormatter(logging.Formatter):
    """Formatter that integrates with structlog processors.
    
    This formatter converts log records into structlog's event dictionary
    format and runs them through the configured processor chain.
    
    Examples:
        >>> fmt = StructlogFormatter(processors=[...])
        >>> output = fmt.format(record)
    """
    
    def __init__(
        self,
        processors: list[Any] | None = None,
        exclude: list[str] | None = None,
    ) -> None:
        """Initialize the structlog formatter.
        
        Args:
            processors: List of structlog processors to apply.
            exclude: List of record attributes to exclude.
        """
        super().__init__("")
        self.processors = processors or []
        self.exclude = exclude or []
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record using structlog processors.
        
        Args:
            record: The log record to format.
        
        Returns:
            Processed log string.
        """
        event_dict: dict[str, Any] {
            "event": escape_ansi(record.getMessage()),
            "logger": record.name,
            "level": record.levelname,
            "timestamp": record.created,
        }
        
        # Add extra fields
        standard_attrs = {
            "name", "msg", "args", "created", "relativeCreated", "exc_info",
            "exc_text", "lineno", "msecs", "pathname", "process", "processName",
            "stack_info", "thread", "threadName", "funcName", "levelno", "levelname",
            "message", "module",
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and key not in self.exclude and not key.startswith("_"):
                event_dict[key] = value
        
        # Run through processors
        for processor in self.processors:
            event_dict = processor(None, None, event_dict)
        
        return json.dumps(event_dict, default=str)
```

---

## Step 4: Implement Filters

### 4.1 `filters.py` - Log Filters

```python
"""
Log filters for controlling log output.

This module provides filters for:
- Debug level filtering (based on DEBUG_LEVEL and DEBUG_FOCUS)
- Level-based filtering
- Context-based filtering

Typical usage example:
    from app.logging.filters import DebugFilter
    
    handler.addFilter(DebugFilter(debug_level=2, debug_focus="scores"))
"""

from __future__ import annotations

import logging
from typing import Any

from app.logging.levels import LogLevel


class DebugFilter(logging.Filter):
    """Filter that controls debug output based on level and focus.
    
    This filter implements the custom debug filtering system that allows
    developers to focus on specific components at specific verbosity levels.
    
    The filter checks for a 'debug' extra field in the log record:
        log("message", extra={"debug": {"level": 2, "focus": "scores"}})
    
    Attributes:
        debug_level: Maximum debug level to show (0-3).
        debug_focus: Component focus for debug logs.
    
    Examples:
        >>> filt = DebugFilter(debug_level=2, debug_focus="all")
        >>> # Records with debug level <= 2 will pass
    """
    
    def __init__(
        self,
        debug_level: int = 0,
        debug_focus: str = "all",
    ) -> None:
        """Initialize the debug filter.
        
        Args:
            debug_level: Maximum debug level to show.
                0 = INFO only, 1 = DBGLV1, 2 = DBGLV2, 3 = VERBOSE
            debug_focus: Component to focus on, or "all" for everything.
        """
        super().__init__()
        self.debug_level = debug_level
        self.debug_focus = debug_focus
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Determine if the record should be logged.
        
        Args:
            record: The log record to check.
        
        Returns:
            True if the record should be logged, False otherwise.
        """
        # Get debug info from extra fields
        debug_info = getattr(record, "debug", None)
        if debug_info is None:
            # No debug info, allow the record
            return True
        
        record_level = debug_info.get("level", 0)
        record_focus = debug_info.get("focus", "all")
        
        # Check if level is sufficient
        if record_level > self.debug_level:
            return False
        
        # Check if focus matches
        if self.debug_focus != "all" and self.debug_focus != record_focus:
            return False
        
        return True


class LevelFilter(logging.Filter):
    """Filter that only allows specific log levels.
    
    This is useful for creating handlers that only output certain levels.
    
    Examples:
        >>> filt = LevelFilter(min_level=logging.WARNING)
        >>> # Only WARNING and above will pass
    """
    
    def __init__(
        self,
        min_level: int = logging.NOTSET,
        max_level: int = logging.CRITICAL,
    ) -> None:
        """Initialize the level filter.
        
        Args:
            min_level: Minimum log level to allow.
            max_level: Maximum log level to allow.
        """
        super().__init__()
        self.min_level = min_level
        self.max_level = max_level
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Check if the record's level is within range.
        
        Args:
            record: The log record to check.
        
        Returns:
            True if the record's level is within the allowed range.
        """
        return self.min_level <= record.levelno <= self.max_level
```

---

## Step 5: Implement Main Logger API

### 5.1 `logger.py` - Main Log Function and Builder

```python
"""
Main logging API.

This module provides the primary logging functions:
- log(): Simple logging function (backward compatible)
- LogBuilder: Builder pattern for complex log entries
- get_logger(): Get a structlog logger wrapper

Typical usage example:
    from app.logging import log, LogBuilder, get_logger
    
    # Simple usage
    log("Server started", level=logging.INFO, color=Ansi.LGREEN)
    
    # Builder pattern
    LogBuilder("Score submitted")
        .with_level(logging.INFO)
        .with_player(player_id=123)
        .with_extra({"score_id": 456, "pp": 150.5})
        .log()
    
    # Structlog wrapper
    logger = get_logger("scores")
    logger.info("Score processed", score_id=123)
"""

from __future__ import annotations

import inspect
import logging
from typing import Any

from app.logging.ansi import Ansi, escape_ansi, get_level_color
from app.logging.config import LoggingConfig
from app.logging.context import get_context_dict

# Global configuration (set during initialization)
_config = LoggingConfig()


def configure(config: LoggingConfig) -> None:
    """Configure the logging system.
    
    Args:
        config: Logging configuration.
    
    Examples:
        >>> from app.logging.config import LoggingConfig
        >>> configure(LoggingConfig(service_name="my_app", debug_level=2))
    """
    global _config
    _config = config
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Configure handlers based on config
    # (Implementation depends on your specific needs)


def log(
    msg: str,
    *,
    level: int = logging.INFO,
    color: Ansi | None = None,
    extra: dict[str, Any] | None = None,
    exc_info: bool = False,
    logger: str | None = None,
) -> None:
    """Log a message with optional color and context.
    
    This is the primary logging function. It provides a simple API
    for logging messages with automatic context inclusion.
    
    Args:
        msg: The message to log.
        level: Log level (use logging module constants).
        color: Optional ANSI color for console output.
            If None, color is determined by level.
        extra: Additional fields to include in structured logs.
        exc_info: Whether to include exception information.
        logger: Logger name to use. Defaults to caller's module.
    
    Examples:
        >>> log("Server started", color=Ansi.LGREEN)
        >>> log("Error occurred", level=logging.ERROR, exc_info=True)
        >>> log("Player action", extra={"player_id": 123, "action": "login"})
    """
    # Get logger
    if logger:
        log_obj = logging.getLogger(logger)
    else:
        # Try to determine caller's module
        frame = inspect.currentframe()
        if frame and frame.f_back:
            module = inspect.getmodule(frame.f_back)
            logger_name = module.__name__ if module else "root"
        else:
            logger_name = "root"
        log_obj = logging.getLogger(logger_name)
    
    # Build extra dict with context
    extra_dict = dict(extra) if extra else {}
    extra_dict.update(get_context_dict())
    
    # Add color info for formatters
    if color is None:
        color = get_level_color(level)
    
    # Log the message
    log_obj.log(level, msg, extra=extra_dict, exc_info=exc_info)


class LogBuilder:
    """Builder for complex log entries with multiple context fields.
    
    This builder provides a fluent API for constructing log entries
    with multiple context fields.
    
    Usage:
        LogBuilder("Score submitted")
            .with_level(logging.INFO)
            .with_player(player_id=123)
            .with_extra({"score_id": score.id, "pp": score.pp})
            .with_request_id(request_id)
            .log()
    
    Examples:
        >>> builder = LogBuilder("Test message")
        >>> builder.with_level(logging.WARNING).log()
    """
    
    def __init__(self, msg: str) -> None:
        """Initialize the log builder.
        
        Args:
            msg: The log message.
        """
        self._msg = msg
        self._level = logging.INFO
        self._color: Ansi | None = None
        self._extra: dict[str, Any] = {}
        self._exc_info = False
        self._logger: str | None = None
    
    def with_level(self, level: int) -> LogBuilder:
        """Set the log level.
        
        Args:
            level: Log level.
        
        Returns:
            Self for chaining.
        """
        self._level = level
        return self
    
    def with_color(self, color: Ansi) -> LogBuilder:
        """Set the console color.
        
        Args:
            color: ANSI color.
        
        Returns:
            Self for chaining.
        """
        self._color = color
        return self
    
    def with_extra(self, **kwargs: Any) -> LogBuilder:
        """Add extra fields.
        
        Args:
            **kwargs: Extra fields to include.
        
        Returns:
            Self for chaining.
        """
        self._extra.update(kwargs)
        return self
    
    def with_player(self, player_id: int) -> LogBuilder:
        """Add player context.
        
        Args:
            player_id: Player ID.
        
        Returns:
            Self for chaining.
        """
        self._extra["player_id"] = player_id
        return self
    
    def with_request_id(self, request_id: str) -> LogBuilder:
        """Add request ID.
        
        Args:
            request_id: Request ID.
        
        Returns:
            Self for chaining.
        """
        self._extra["request_id"] = request_id
        return self
    
    def with_exception(self, exc_info: bool = True) -> LogBuilder:
        """Include exception info.
        
        Args:
            exc_info: Whether to include exception info.
        
        Returns:
            Self for chaining.
        """
        self._exc_info = exc_info
        return self
    
    def with_logger(self, logger: str) -> LogBuilder:
        """Set logger name.
        
        Args:
            logger: Logger name.
        
        Returns:
            Self for chaining.
        """
        self._logger = logger
        return self
    
    def log(self) -> None:
        """Execute the log operation.
        
        Examples:
            >>> LogBuilder("Test").with_level(logging.INFO).log()
        """
        log(
            self._msg,
            level=self._level,
            color=self._color,
            extra=self._extra,
            exc_info=self._exc_info,
            logger=self._logger,
        )
```

---

## Step 6: Implement Structlog Wrapper

### 6.1 `structlog_wrapper.py` - Structlog Integration

```python
"""
Structlog integration wrapper.

This module provides a clean API for using structlog with our
custom logging configuration.

Typical usage example:
    from app.logging import get_logger
    
    logger = get_logger("scores")
    logger.info("Score submitted", score_id=123, pp=150.5)
    logger.error("Validation failed", error="invalid score")
"""

from __future__ import annotations

from typing import Any

import structlog

from app.logging.config import LoggingConfig
from app.logging.context import get_context_dict
from app.logging.levels import register_custom_levels


def setup_structlog(config: LoggingConfig) -> None:
    """Configure structlog with our custom settings.
    
    Args:
        config: Logging configuration.
    
    Examples:
        >>> from app.logging.config import LoggingConfig
        >>> setup_structlog(LoggingConfig(service_name="my_app"))
    """
    register_custom_levels()
    
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
            _add_context_processor,
            structlog.stdlib.render_to_log_kwargs,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def _add_context_processor(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add request context to all structlog entries.
    
    This processor automatically includes request context (request_id,
    player_id, etc.) in all log entries.
    
    Args:
        logger: The logger instance.
        method_name: The logging method name.
        event_dict: The event dictionary being built.
    
    Returns:
        Updated event dictionary with context.
    """
    context = get_context_dict()
    event_dict.update(context)
    return event_dict


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger with our custom configuration.
    
    Args:
        name: Logger name (typically module name).
    
    Returns:
        Configured structlog logger.
    
    Examples:
        >>> logger = get_logger("scores")
        >>> logger.info("Score processed", score_id=123)
    """
    return structlog.get_logger(name)
```

---

## Step 7: Implement Plugins

### 7.1 `plugins/request_formatters.py` - HTTP Request Formatters

```python
"""
HTTP request formatters for logging.

This module provides formatters for extracting loggable information
from HTTP request objects. It supports multiple frameworks through
a plugin registration system.

Typical usage example:
    from app.logging.plugins.request_formatters import register_formatter
    from my_framework import MyRequestFormatter
    
    register_formatter(MyRequestFormatter())
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class RequestFormatter(ABC):
    """Base class for HTTP request formatters.
    
    Subclass this to add support for different frameworks.
    
    Examples:
        class FastAPIRequestFormatter(RequestFormatter):
            def can_handle(self, request):
                return hasattr(request, 'method') and hasattr(request, 'headers')
            
            def format(self, request):
                return {"method": request.method, "path": request.url.path}
    """
    
    @abstractmethod
    def can_handle(self, request: Any) -> bool:
        """Check if this formatter can handle the given request.
        
        Args:
            request: The request object to check.
        
        Returns:
            True if this formatter can handle the request.
        """
        ...
    
    @abstractmethod
    def format(self, request: Any) -> dict[str, Any]:
        """Format the request into a dictionary for logging.
        
        Args:
            request: The request object to format.
        
        Returns:
            Dictionary with request information.
        """
        ...


# Registry of formatters
_formatters: list[RequestFormatter] = []


def register_formatter(formatter: RequestFormatter) -> None:
    """Register a request formatter.
    
    Args:
        formatter: The formatter to register.
    
    Examples:
        >>> register_formatter(FastAPIRequestFormatter())
    """
    _formatters.append(formatter)


def format_request(request: Any) -> dict[str, Any]:
    """Format a request using the appropriate registered formatter.
    
    Args:
        request: The request object to format.
    
    Returns:
        Dictionary with request information, or empty dict if no formatter found.
    
    Examples:
        >>> info = format_request(request)
        >>> print(info["method"], info["path"])
    """
    for formatter in _formatters:
        if formatter.can_handle(request):
            return formatter.format(request)
    return {}


class FastAPIRequestFormatter(RequestFormatter):
    """Formatter for FastAPI Request objects.
    
    Extracts relevant information from FastAPI requests for logging.
    Excludes sensitive headers like Authorization and Cookie.
    
    Examples:
        >>> formatter = FastAPIRequestFormatter()
        >>> if formatter.can_handle(request):
        ...     info = formatter.format(request)
    """
    
    # Headers to exclude from logs
    EXCLUDED_HEADERS = {
        "accept-encoding",
        "cf-ray",
        "cf-warp-tag-id",
        "connection",
        "x-forwarded-server",
        "authorization",
        "cookie",
    }
    
    def can_handle(self, request: Any) -> bool:
        """Check if this is a FastAPI request.
        
        Args:
            request: Object to check.
        
        Returns:
            True if the object appears to be a FastAPI request.
        """
        return (
            hasattr(request, "method")
            and hasattr(request, "headers")
            and hasattr(request, "url")
        )
    
    def format(self, request: Any) -> dict[str, Any]:
        """Format a FastAPI request.
        
        Args:
            request: FastAPI request object.
        
        Returns:
            Dictionary with request information.
        """
        headers = dict(request.headers)
        safe_headers = {
            k: v for k, v in headers.items()
            if k.lower() not in self.EXCLUDED_HEADERS
        }
        
        return {
            "method": request.method,
            "path": str(request.url.path),
            "query_params": dict(request.query_params),
            "headers": safe_headers,
            "client_ip": headers.get("x-forwarded-for", headers.get("x-real-ip", "unknown")),
        }
```

### 7.2 `plugins/error_handler.py` - Error Catcher Decorator

```python
"""
Error handler decorator for automatic exception logging.

This module provides a decorator that catches exceptions and logs them
with full context information. It's designed to work with the logging
package but can be used independently.

Typical usage example:
    from app.logging.plugins.error_handler import error_catcher
    
    @error_catcher
    async def process_score(score_data):
        ...
    
    @error_catcher(logger="scores", reraise=False)
    async def validate_score(score_data):
        ...
"""

from __future__ import annotations

import asyncio
import functools
import logging
import sys
import traceback
from typing import Any, Callable, TypeVar, cast

from app.logging import log

P = TypeVar("P")
R = TypeVar("R")


def error_catcher(
    func: Callable[..., R] | None = None,
    *,
    logger: str | None = None,
    level: int = logging.ERROR,
    reraise: bool = True,
) -> Callable[..., R] | Callable[[Callable[..., R]], Callable[..., R]]:
    """Decorator that catches and logs exceptions with full context.
    
    This decorator wraps functions to catch any exceptions, log them
    with detailed context information, and optionally re-raise them.
    
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
    
    Examples:
        >>> @error_catcher
        ... async def risky_operation():
        ...     raise ValueError("Something went wrong")
        
        >>> @error_catcher(reraise=False)
        ... def safe_operation():
        ...     raise RuntimeError("Non-critical error")
    """
    
    def decorator(fn: Callable[..., R]) -> Callable[..., R]:
        nonlocal logger
        if logger is None:
            logger = getattr(fn, "__module__", "unknown")
        
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> R:
                try:
                    return await fn(*args, **kwargs)
                except Exception as e:
                    _log_exception(e, fn, logger, level, args, kwargs)
                    if reraise:
                        raise
                    return cast(R, None)
            
            # Preserve __globals__ for forward reference resolution
            async_wrapper.__globals__.update(getattr(fn, "__globals__", {}))
            return async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> R:
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    _log_exception(e, fn, logger, level, args, kwargs)
                    if reraise:
                        raise
                    return cast(R, None)
            
            sync_wrapper.__globals__.update(getattr(fn, "__globals__", {}))
            return sync_wrapper
    
    if func is not None:
        # Called without parentheses: @error_catcher
        return decorator(func)
    # Called with parentheses: @error_catcher(...)
    return decorator


def _log_exception(
    exc: Exception,
    func: Callable[..., Any],
    logger: str,
    level: int,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> None:
    """Log an exception with full context.
    
    Args:
        exc: The exception that was raised.
        func: The function that raised the exception.
        logger: Logger name to use.
        level: Log level.
        args: Positional arguments passed to the function.
        kwargs: Keyword arguments passed to the function.
    """
    exc_type, exc_value, exc_traceback = sys.exc_info()
    
    # Build context
    context = {
        "function_name": getattr(func, "__name__", "unknown"),
        "function_module": getattr(func, "__module__", "unknown"),
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "traceback": "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
    }
    
    # Add args/kwargs info (be careful with sensitive data)
    if args:
        context["args_count"] = len(args)
    if kwargs:
        context["kwargs_keys"] = list(kwargs.keys())
    
    log(
        f"Error in {context['function_name']}: {exc}",
        level=level,
        extra=context,
        exc_info=True,
        logger=logger,
    )
```

---

## Step 8: Implement Testing Utilities

### 8.1 `testing.py` - Test Helpers

```python
"""
Testing utilities for the logging package.

This module provides helpers for testing code that uses the logging system.
It includes log capture, assertions, and pytest fixtures.

Typical usage example:
    from app.logging.testing import LogCapture, assert_log_contains
    
    def test_my_function():
        with LogCapture() as capture:
            my_function()
            assert capture.has_message("Expected message")
            assert capture.count_level(logging.WARNING) == 1
"""

from __future__ import annotations

import logging
from io import StringIO
from typing import Any


class LogCapture:
    """Context manager for capturing log output in tests.
    
    This class captures all log output made during its context,
    allowing you to assert on log messages, levels, and counts.
    
    Usage:
        with LogCapture() as capture:
            log("Test message", level=logging.INFO)
            assert capture.has_message("Test message")
            assert capture.count_messages(level=logging.INFO) == 1
    
    Examples:
        >>> with LogCapture() as capture:
        ...     logging.info("Hello")
        ...     logging.warning("World")
        >>> capture.count_messages()
        2
    """
    
    def __init__(
        self,
        level: int = logging.DEBUG,
        logger: str | None = None,
    ) -> None:
        """Initialize log capture.
        
        Args:
            level: Minimum log level to capture.
            logger: Logger name to capture from. None for root logger.
        """
        self.level = level
        self.logger_name = logger
        self.records: list[logging.LogRecord] = []
        self._handler: logging.Handler | None = None
        self._logger: logging.Logger | None = None
    
    def __enter__(self) -> LogCapture:
        """Start capturing logs.
        
        Returns:
            Self for use in 'as' clause.
        """
        self._logger = logging.getLogger(self.logger_name)
        self._handler = _CaptureHandler(self.records)
        self._handler.setLevel(self.level)
        self._logger.addHandler(self._handler)
        return self
    
    def __exit__(self, *args: Any) -> None:
        """Stop capturing logs."""
        if self._logger and self._handler:
            self._logger.removeHandler(self._handler)
    
    def has_message(self, message: str, exact: bool = False) -> bool:
        """Check if a message was logged.
        
        Args:
            message: Message to search for.
            exact: If True, match exact message. If False, check if contained.
        
        Returns:
            True if the message was found.
        
        Examples:
            >>> with LogCapture() as capture:
            ...     logging.info("Hello World")
            >>> capture.has_message("Hello")
            True
            >>> capture.has_message("Hello World", exact=True)
            True
        """
        for record in self.records:
            if exact:
                if record.getMessage() == message:
                    return True
            else:
                if message in record.getMessage():
                    return True
        return False
    
    def count_messages(
        self,
        message: str | None = None,
        level: int | None = None,
    ) -> int:
        """Count logged messages matching criteria.
        
        Args:
            message: Message to search for (optional).
            level: Log level to filter by (optional).
        
        Returns:
            Number of matching messages.
        
        Examples:
            >>> with LogCapture() as capture:
            ...     logging.info("A")
            ...     logging.info("B")
            ...     logging.warning("C")
            >>> capture.count_messages()
            3
            >>> capture.count_messages(level=logging.INFO)
            2
        """
        count = 0
        for record in self.records:
            if level is not None and record.levelno != level:
                continue
            if message is not None and message not in record.getMessage():
                continue
            count += 1
        return count
    
    def count_level(self, level: int) -> int:
        """Count messages at a specific level.
        
        Args:
            level: Log level to count.
        
        Returns:
            Number of messages at that level.
        
        Examples:
            >>> with LogCapture() as capture:
            ...     logging.warning("Warning!")
            >>> capture.count_level(logging.WARNING)
            1
        """
        return self.count_messages(level=level)
    
    def get_messages(self) -> list[str]:
        """Get all logged messages.
        
        Returns:
            List of message strings.
        
        Examples:
            >>> with LogCapture() as capture:
            ...     logging.info("Hello")
            >>> capture.get_messages()
            ['Hello']
        """
        return [r.getMessage() for r in self.records]
    
    def get_records(self) -> list[logging.LogRecord]:
        """Get all log records.
        
        Returns:
            List of LogRecord objects.
        """
        return self.records.copy()
    
    def clear(self) -> None:
        """Clear captured records.
        
        Examples:
            >>> with LogCapture() as capture:
            ...     logging.info("Hello")
            ...     capture.clear()
            >>> capture.count_messages()
            0
        """
        self.records.clear()


class _CaptureHandler(logging.Handler):
    """Handler that captures log records to a list."""
    
    def __init__(self, records: list[logging.LogRecord]) -> None:
        """Initialize the capture handler.
        
        Args:
            records: List to store captured records.
        """
        super().__init__()
        self.records = records
    
    def emit(self, record: logging.LogRecord) -> None:
        """Capture a log record.
        
        Args:
            record: The log record to capture.
        """
        self.records.append(record)


def assert_log_contains(
    records: list[logging.LogRecord],
    message: str | None = None,
    level: int | None = None,
    **extra_fields: Any,
) -> bool:
    """Assert that log records contain a matching entry.
    
    Args:
        records: List of log records to search.
        message: Message to search for.
        level: Log level to match.
        **extra_fields: Extra fields to match.
    
    Returns:
        True if a matching record is found.
    
    Raises:
        AssertionError: If no matching record is found.
    
    Examples:
        >>> records = [logging.LogRecord("test", 20, "", 0, "msg", (), None)]
        >>> assert_log_contains(records, message="msg", level=20)
        True
    """
    for record in records:
        if message and message not in record.getMessage():
            continue
        if level is not None and record.levelno != level:
            continue
        
        # Check extra fields
        fields_match = True
        for key, value in extra_fields.items():
            if not hasattr(record, key) or getattr(record, key) != value:
                fields_match = False
                break
        
        if fields_match:
            return True
    
    raise AssertionError(
        f"No log record found matching: message={message}, level={level}, extra={extra_fields}"
    )


# Pytest fixtures (if pytest is available)
try:
    import pytest
    
    @pytest.fixture
    def log_capture():
        """Pytest fixture for log capture.
        
        Yields:
            LogCapture instance.
        
        Examples:
            def test_something(log_capture):
                with log_capture:
                    do_something()
                    assert log_capture.has_message("Expected")
        """
        with LogCapture() as capture:
            yield capture

except ImportError:
    pass
```

---

## Step 9: Create Package `__init__.py`

### 9.1 `app/logging/__init__.py` - Public API

```python
"""
Logging package for bancho.py.

This package provides a comprehensive logging system with:
- Simple log() function for basic usage
- LogBuilder for complex log entries
- Request context and correlation IDs
- Multiple output formats (console, JSON, structured)
- Debug filtering by level and focus
- Test utilities

Quick Start:
    from app.logging import log, Ansi, configure
    from app.logging.config import LoggingConfig
    
    # Configure logging
    configure(LoggingConfig(service_name="my_app", debug_level=2))
    
    # Simple logging
    log("Server started", color=Ansi.LGREEN)
    log("Error occurred", level=logging.ERROR, exc_info=True)
    
    # With context
    with LogContext(request_id="abc123", player_id=456):
        log("Processing score")  # Includes request_id and player_id

Advanced Usage:
    from app.logging import LogBuilder, get_logger
    
    # Builder pattern
    LogBuilder("Score submitted")
        .with_level(logging.INFO)
        .with_player(player_id=123)
        .with_extra({"score_id": 456})
        .log()
    
    # Structlog
    logger = get_logger("scores")
    logger.info("Score processed", score_id=123)
"""

from __future__ import annotations

# Configuration
from app.logging.config import LoggingConfig

# Log levels
from app.logging.levels import LogLevel, register_custom_levels

# ANSI colors
from app.logging.ansi import Ansi, colorize, escape_ansi

# Context management
from app.logging.context import (
    LogContext,
    RequestContext,
    clear_context,
    generate_request_id,
    get_correlation_id,
    get_current_context,
    get_player_id,
    get_request_id,
)

# Main logging functions
from app.logging.logger import LogBuilder, configure, log

# Structlog integration
from app.logging.structlog_wrapper import get_logger, setup_structlog

# Filters
from app.logging.filters import DebugFilter, LevelFilter

# Formatters
from app.logging.formatters import ConsoleFormatter, JsonFormatter, StructlogFormatter

# Plugins
from app.logging.plugins.error_handler import error_catcher
from app.logging.plugins.request_formatters import (
    FastAPIRequestFormatter,
    RequestFormatter,
    format_request,
    register_formatter,
)

# Testing utilities
from app.logging.testing import LogCapture, assert_log_contains

__all__ = [
    # Configuration
    "LoggingConfig",
    
    # Log levels
    "LogLevel",
    "register_custom_levels",
    
    # ANSI colors
    "Ansi",
    "colorize",
    "escape_ansi",
    
    # Context
    "LogContext",
    "RequestContext",
    "clear_context",
    "generate_request_id",
    "get_correlation_id",
    "get_current_context",
    "get_player_id",
    "get_request_id",
    
    # Main API
    "LogBuilder",
    "configure",
    "log",
    
    # Structlog
    "get_logger",
    "setup_structlog",
    
    # Filters
    "DebugFilter",
    "LevelFilter",
    
    # Formatters
    "ConsoleFormatter",
    "JsonFormatter",
    "StructlogFormatter",
    
    # Plugins
    "error_catcher",
    "FastAPIRequestFormatter",
    "RequestFormatter",
    "format_request",
    "register_formatter",
    
    # Testing
    "LogCapture",
    "assert_log_contains",
]
```

---

## Step 10: Migration Guide

### 10.1 Backward Compatibility

Create a compatibility module for gradual migration:

```python
# app/logging/compat.py
"""
Backward compatibility layer for the old logging API.

This module provides compatibility with the old app/logging.py API.
It will be removed in a future version.

Deprecated:
    - Direct imports from app.logging (use app.logging instead)
    - Old log() signature with positional color argument
"""

import warnings
from app.logging import Ansi, log as new_log


def log(msg, start_color=None, extra=None, logger="", level=20, *args, **kwargs):
    """Deprecated: Use app.logging.log() instead."""
    warnings.warn(
        "This log() signature is deprecated. Use app.logging.log() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Convert old signature to new
    return new_log(
        msg,
        level=level,
        color=start_color,
        extra=extra,
        logger=logger,
    )
```

### 10.2 Import Migration Map

| Old Import | New Import |
|------------|------------|
| `from app.logging import log` | `from app.logging import log` |
| `from app.logging import Ansi` | `from app.logging import Ansi` |
| `from app.logging import logLevel` | `from app.logging.levels import LogLevel` |
| `from app.logging import error_catcher` | `from app.logging.plugins.error_handler import error_catcher` |
| `from app.logging import format_request` | `from app.logging.plugins.request_formatters import format_request` |

---

## Implementation Order

1. **Create package structure** (Step 1)
2. **Implement core modules** (Step 2): config, levels, ansi, context
3. **Implement formatters** (Step 3)
4. **Implement filters** (Step 4)
5. **Implement main logger** (Step 5)
6. **Implement structlog wrapper** (Step 6)
7. **Implement plugins** (Step 7)
8. **Implement testing utilities** (Step 8)
9. **Create package __init__.py** (Step 9)
10. **Write tests for all modules**
11. **Create migration guide** (Step 10)
12. **Gradual migration of existing code**

---

## Testing Requirements

Each module should have corresponding tests:

```
tests/unit/logging/
├── __init__.py
├── test_config.py
├── test_levels.py
├── test_ansi.py
├── test_context.py
├── test_filters.py
├── test_formatters.py
├── test_logger.py
├── test_structlog_wrapper.py
├── test_error_handler.py
├── test_request_formatters.py
└── test_testing_utils.py
```

---

## Success Criteria

- [ ] All modules implemented with comprehensive docstrings
- [ ] All public APIs have type hints
- [ ] Test coverage > 90%
- [ ] All existing tests pass
- [ ] New functionality tested
- [ ] Backward compatibility maintained
- [ ] Documentation complete
