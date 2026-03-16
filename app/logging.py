"""
Logging Module - Comprehensive Logging and Error Handling System

This module provides a comprehensive logging and error handling system for the
osu! server application, implementing structured logging with multiple output
formats, color-coded console output, and advanced error tracking capabilities.
It serves as the central logging infrastructure for the entire application.

The module integrates Python's standard logging with structlog for structured
logging, providing both human-readable console output and machine-parseable
JSON logs. It includes custom formatters, handlers, and utilities for
debugging, monitoring, and error reporting.

Key Features:
    - Structured logging with structlog integration
    - Color-coded console output with ANSI escape codes
    - JSON-formatted log output for machine processing
    - Custom log levels (VERBOSE, DBGLV2, DBGLV1)
    - Debug filtering based on configuration
    - Error catching decorator for exception handling
    - Request formatting for HTTP logging
    - IP address resolution and caching
    - Stack trace capture and formatting
    - Circular reference detection in serialization

Integration Points:
    - Settings configuration in app/settings.py
    - IP resolution for geolocation in app/state/services.py
    - FastAPI request handling in app/api/
    - Error handling throughout the application
    - Debug configuration in app/settings.py

Log Levels:
    - DEBUG (10): Detailed diagnostic information
    - VERBOSE (11): Extended diagnostic information
    - DBGLV2 (14): Debug level 2 information
    - DBGLV1 (16): Debug level 1 information
    - INFO (20): General operational information
    - WARNING (30): Potential issues or important notices
    - ERROR (40): Error conditions that need attention
    - CRITICAL (50): Critical errors that may cause shutdown

Usage Pattern:
    # Basic logging
    from app.logging import log, Ansi
    log("Server started", Ansi.LGREEN)
    
    # Error logging with context
    log("Database connection failed", Ansi.LRED, extra={
        "error": str(e),
        "host": db_host,
        "port": db_port
    })
    
    # Debug logging with filtering
    log("Processing request", Ansi.LBLUE, extra={
        "filter": {"debugLevel": 2, "debugFocus": "requests"}
    })
    
    # Error catching decorator
    @error_catcher
    async def risky_function():
        # Function that might raise exceptions
        pass

Related Files:
    - app/settings.py: Logging configuration settings
    - app/state/services.py: IP resolution and geolocation
    - app/api/: HTTP request logging
    - app/utils.py: Utility functions for logging
"""

from __future__ import annotations

import sys
import logging.config
from logging.handlers import HTTPHandler
import re
from collections.abc import Mapping
from collections.abc import MutableMapping
from enum import IntEnum
from zoneinfo import ZoneInfo

from requests import request
import yaml, os
import json
import jsons  # type: ignore[import-untyped]
from app import settings
from app._typing import IPAddress
import structlog
import structlog.stdlib
import importlib
import datetime
import inspect
from pythonjsonlogger import jsonlogger
from logging import Handler
import traceback
import time
import asyncio
import functools
from typing import Any, TypeVar, ParamSpec, Callable, NoReturn, Coroutine, overload, cast
import types

# Incredibly Stupid Required Imports for Error_Catcher
from fastapi import status
from fastapi.datastructures import FormData
from fastapi.datastructures import UploadFile
from fastapi.exceptions import HTTPException
from fastapi.param_functions import Depends
from fastapi.param_functions import File
from fastapi.param_functions import Form
from fastapi.param_functions import Header
from fastapi.param_functions import Path
from fastapi.param_functions import Query
from fastapi.requests import Request
from fastapi.responses import FileResponse
from fastapi.responses import ORJSONResponse
from fastapi.responses import RedirectResponse
from fastapi.responses import Response
from fastapi.routing import APIRouter
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette import status

# Stupid Dumb Fucking Json Serialization BS IMPORTS OMFG I'M LOSING MY MIND
import decimal
from ipaddress import IPv4Network, IPv4Address, ip_address

class IPResolver:
    def __init__(self) -> None:
        self.cache: MutableMapping[str, IPAddress] = {}

    def get_ip(self, headers: Mapping[str, str]) -> IPAddress:
        """Resolve the IP address from the headers."""
        ip_str = headers.get("CF-Connecting-IP")
        if ip_str is None:
            forwards = headers.get("X-Forwarded-For", "").split(",")

            if forwards != [""]:
                ip_str = forwards[0]
            else:
                ip_str = headers.get("X-Real-IP", "")

        ip = self.cache.get(ip_str)
        if ip is None:
            if ip_str != '':
                ip = ip_address(ip_str)
                self.cache[ip_str] = ip
            else:
                ip = ip_address("127.0.0.1")

        return ip

ip_resolver: IPResolver = IPResolver()

def ipv4network_serializer(obj: IPv4Network, **kwargs: Any) -> str:
    return str(obj)

def ipv4address_serializer(obj: IPv4Address, **kwargs: Any) -> str:
    return str(obj)

jsons.set_serializer(ipv4network_serializer, IPv4Network)
jsons.set_serializer(ipv4address_serializer, IPv4Address)

def setup_logging(default_path: str = 'logging.yaml', default_level: int = logging.INFO, env_key: str = 'LOG_CFG') -> None:
    """Setup logging configuration"""
    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)

def setup_structlog() -> None:
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

def configure_logging() -> None:
    setup_logging()
    setup_structlog()

def serialize_value(value: Any, seen: set[int] | None = None) -> Any:
    """Serialize a value to a JSON-compatible format, extracting meaningful information from objects."""
    if seen is None:
        seen = set()
    
    try:
        # Handle basic types first
        if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
            return value.isoformat()
        elif isinstance(value, decimal.Decimal):
            return float(value)
        elif isinstance(value, bytes):
            return value.decode('utf-8')
        elif isinstance(value, (int, float, str, bool, type(None))):
            return value
        elif isinstance(value, (list, set, tuple)):
            return [serialize_value(item, seen) for item in value]
        elif isinstance(value, dict):
            return {str(key): serialize_value(val, seen) for key, val in value.items()}
        
        # Handle Request objects specially
        if hasattr(value, '__class__') and (
            (hasattr(value, 'method') and hasattr(value, 'headers') and hasattr(value, 'path')) or
            type(value).__name__ == 'Request'
        ):
            # This is likely a Request object, format it properly
            try:
                return format_request(value)
            except Exception:
                pass
        
        # Handle complex objects
        if id(value) in seen:
            return f"<Circular Reference: {type(value).__name__} id={id(value)}>"
        
        seen.add(id(value))
        
        # Try to extract meaningful information from objects
        if hasattr(value, '__dict__'):
            # For objects with __dict__, extract key attributes
            obj_info = {
                '__type__': type(value).__name__,
                '__module__': getattr(value, '__module__', None),
            }
            
            # Try to get a name or identifier
            if hasattr(value, 'name'):
                obj_info['name'] = value.name
            elif hasattr(value, 'id'):
                obj_info['id'] = value.id
            elif hasattr(value, 'username'):
                obj_info['username'] = value.username
            elif hasattr(value, 'title'):
                obj_info['title'] = value.title
            
            # Add a string representation without memory address
            str_repr = str(value)
            # Remove memory address from repr if present
            if ' at 0x' in str_repr:
                str_repr = f"<{type(value).__name__}>"
            obj_info['repr'] = str_repr
            
            return obj_info
        else:
            # For objects without __dict__, use string representation
            str_repr = str(value)
            # Remove memory address from repr if present
            if ' at 0x' in str_repr:
                return f"<{type(value).__name__}>"
            return str_repr
            
    except Exception:
        # If anything fails, return a safe string representation
        try:
            return str(value)
        except:
            return f"<Unserializable: {type(value).__name__}>"

def serialize_record(record: Any, seen: set[int] | None = None) -> dict[Any, Any]:
    if seen is None:
        seen = set()
    seen.add(id(record))

    def serialize(value: Any) -> Any:
        return serialize_value(value, seen)

    serializable_record: dict[Any, Any] = {}
    for key, value in record.__dict__.items():
        serializable_record[key] = serialize(value)

    return serializable_record

class BytesJsonFormatter(jsonlogger.JsonFormatter):
    def format(self, record: logging.LogRecord) -> bytes: # type: ignore[override]
        # Convert only keys and values that are not of type str, int, float, bool, or None
        record.__dict__ = {
            str(k) if not isinstance(k, (str, int, float, bool, type(None))) else k: # type: ignore[redundant-expr]
            str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
            for k, v in record.__dict__.items()
        }

        # Check if the message contains any placeholders as this throws an error when formatting on string_record
        if not re.search(r'%\(.+?\)s', record.msg) and record.args:
            record.args = None

        string_record = super().format(record)
        return string_record.encode('utf-8')


console_logger = logging.getLogger('console')
console_handlers = console_logger.handlers

def get_timestamp(full: bool = False, tz: ZoneInfo | None = None) -> str:
    fmt = "%d/%m/%Y %I:%M:%S%p" if full else "%I:%M:%S%p"
    return f"{datetime.datetime.now(tz=tz):{fmt}}"

def fromtimestamp(timestamp: float) -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))

ANSI_ESCAPE_REGEX = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]")
def escape_ansi(line: str) -> str:
    return ANSI_ESCAPE_REGEX.sub("", line)

class Ansi(IntEnum):
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
        return f"\x1b[{self.value}m"

class logLevel(IntEnum):
    """
    Represents the log levels for Pythons Built in logger.

    DEBUG (10): Detailed information, typically useful only for diagnosing problems.
    VERBOSE (11): Detailed information, typically useful only for diagnosing problems.
    INFO (20): General information about the execution of the program.
    WARNING (30): Indicates a potential issue or something that should be brought to attention.
    ERROR (40): Indicates a more serious problem that prevented the program from functioning.
    CRITICAL (50): Indicates a critical error that may cause the program to terminate.

    """

    DEBUG = 10
    VERBOSE = 11
    DBGLV2 = 14
    DBGLV1 = 16
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

    def __repr__(self) -> str:
        return f"\x1b[{self.value}m"
    
    @classmethod
    def add_Log_Levels(cls) -> None:
        logging.addLevelName(cls.VERBOSE, 'VERBOSE')
        logging.addLevelName(cls.DBGLV2, 'DBGLV2')
        logging.addLevelName(cls.DBGLV1, 'DBGLV1')
        # Add the custom log levels to the NAME_TO_LEVEL dictionary in structlog
        # Use getattr to avoid type checking issues with non-exported attribute
        name_to_level = getattr(structlog.stdlib, 'NAME_TO_LEVEL', {})
        name_to_level['verbose'] = cls.VERBOSE
        name_to_level['dbglv2'] = cls.DBGLV2
        name_to_level['dbglv1'] = cls.DBGLV1
logLevel.add_Log_Levels()

class DebugFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Get the 'filter' field from the 'extra' dictionary
        filter_field = record.__dict__.get('filter')
        # If the 'filter' field is not present, don't filter the record
        if filter_field is None:
            return True

        # Get the debug level and focus
        debug_level = filter_field.get('debugLevel', 0)
        debug_focus = filter_field.get('debugFocus', 'all')
        logging.getLogger('console').debug(f"settings.DEBUG_FOCUS: {settings.DEBUG_FOCUS}", extra={'CodeRegion': 'Logging', "Func": "DebugFilter.filter"})
        logging.getLogger('console').debug(f"debug_focus: {debug_focus}", extra={'CodeRegion': 'Logging', "Func": "DebugFilter.filter"})


        # Check if the debug level is sufficient
        if debug_level > settings.DEBUG_LEVEL:
            return False

        # Check if the debug focus is 'all' or matches the logger name
        if settings.DEBUG_FOCUS != 'all' and settings.DEBUG_FOCUS != debug_focus:
            return False

        return True

debug_filter = DebugFilter()
console_logger.addFilter(debug_filter)
# Add filter to each handler
for handler in console_handlers:
    handler.addFilter(debug_filter)
    # Sets Console Logger Level based on current DebugLevel
    if settings.DEBUG_LEVEL == 3:
        handler.setLevel(logLevel.VERBOSE)
    elif settings.DEBUG_LEVEL == 2:
        handler.setLevel(logLevel.DBGLV2)
    elif settings.DEBUG_LEVEL == 1:
        handler.setLevel(logLevel.DBGLV1)
    elif settings.DEBUG_LEVEL == 0:
        handler.setLevel(logLevel.INFO)
    else:
        handler.setLevel(logLevel.DEBUG)

def getHandlerByName(name: str, logger: logging.Logger) -> Handler | None:
    for handler in logger.handlers:
        if handler.get_name() == name:
            return handler
    return None


def _serialize_function_args(args: tuple[Any, ...], extra: dict[str, object]) -> tuple[tuple[Any, ...], dict[str, object]]:
    """Serialize function arguments for logging."""
    if not args:
        return args, extra
    
    # Use the new serialize_value function for proper serialization
    serialized_args = [serialize_value(arg) for arg in args]
    
    extra['extra_args'] = tuple(serialized_args)
    
    return (), extra


def _serialize_locals(arg_info: inspect.ArgInfo, extra: dict[str, object], log_level: int) -> dict[str, object]:
    """Serialize local variables for logging."""
    if log_level < 21:
        return extra
    
    try:
        # Use the new serialize_value function for proper serialization
        serialized_locals = {}
        for k, v in arg_info.locals.items():
            serialized_locals[k] = serialize_value(v)
        
        extra['locals'] = json.dumps(serialized_locals)
    except TypeError:
        # If even the simplified serialization fails, store as string representation
        extra['locals'] = str(arg_info.locals)
    
    return extra


def _add_stack_trace(extra: dict[str, object], log_level: int) -> dict[str, object]:
    """Add stack trace information to the extra fields."""
    # Add stack trace to the 'extra' fields
    extra['stack_trace'] = json.dumps(traceback.format_stack())
    
    if log_level >= 40:
        # Add minimal stack trace information
        stack_info = inspect.stack()
        if stack_info:
            # Only include the immediate caller frame
            caller_frame = stack_info[1] if len(stack_info) > 1 else stack_info[0]
            extra['caller_file'] = caller_frame.filename
            extra['caller_line'] = caller_frame.lineno
            extra['caller_function'] = caller_frame.function
        
        # Add exception info if available
        exc_info = sys.exc_info()
        if exc_info[0] is not None:
            extra['error_type'] = exc_info[0].__name__
            extra['error_message'] = str(exc_info[1])
            extra['stack_trace'] = traceback.format_exc()
    
    return extra


ROOT_LOGGER = logging.getLogger()


def log(
    msg: str,
    start_color: Ansi | None = None,
    extra: Mapping[str, object] | None = None,
    logger: str = '',
    level: int = logging.INFO,
    levelow: bool = False,
    exc_info: bool = False,
    *args: Any,
) -> None:
    """\
    A wrapper for the python logging library to add color formatting and additional
    fields to logs for warnings and errors, while attaching extra fields to the log.
    """

    # Get the logger find a suitable default if one not provided.
    if logger:
        log_obj = structlog.get_logger(logger)
    else:
        if start_color is Ansi.LYELLOW:
            log_obj = structlog.get_logger('console.warn')
        elif start_color is Ansi.LRED:
            log_obj = structlog.get_logger('console.error')
        else:
            if level:
                if level <= 19:
                    log_obj = structlog.get_logger('console.debug')
                else:
                    log_obj = structlog.get_logger('console.info')
            else:
                log_obj = structlog.get_logger('console.info')

    if level == logging.INFO and levelow != True:
        if start_color is Ansi.LYELLOW:
            log_level = logging.WARNING
        elif start_color is Ansi.LRED:
            log_level = logging.ERROR
        else:
            log_level = logging.INFO
    else:
        log_level = level
    

    # TODO: decouple colors from the base logging function; move it to
    # be a formatter-specific concern such that we can log without color.
    if settings.LOG_WITH_COLORS:
        color_prefix = f"{start_color!r}" if start_color is not None else ""
        color_suffix = f"{Ansi.RESET!r}" if start_color is not None else ""
    else:
        msg = escape_ansi(msg)
        color_prefix = color_suffix = ""

    # Get the frame that called this function
    frame = inspect.currentframe()
    if frame is None or frame.f_back is None:
        # Fallback if we can't get the frame
        # Create a simple object with the required attributes
        class FrameInfoFallback:
            filename: str = '<unknown>'
            lineno: int = 0
            function: str = '<unknown>'
        info: inspect.Traceback | FrameInfoFallback = FrameInfoFallback()
    else:
        info = inspect.getframeinfo(frame.f_back)
    
    # Add Timestamp and Message to the 'extra' fields
    extra_dict = dict(extra) if extra else {}
    
    extra_dict['@timestamp'] = datetime.datetime.now().isoformat()
    extra_dict['Message'] = escape_ansi(msg)
    
    # Check if the message contains any placeholders
    if not re.search(r'%\(.+?\)s', msg) and args:
        # Use helper method to serialize function arguments
        args, extra_dict = _serialize_function_args(args, extra_dict)

    # Get the arguments of the calling function
    if frame is not None and frame.f_back is not None:
        arg_info = inspect.getargvalues(frame.f_back)
    else:
        # Fallback if we can't get the frame
        arg_info = inspect.ArgInfo(args=[], varargs=None, keywords=None, locals={})
    
    msg = f"{color_prefix}{msg}{color_suffix}"

    
    # Create a LogRecord with the correct information
    exc_info_value: tuple[type[BaseException], BaseException, types.TracebackType | None] | tuple[None, None, None] | None = None
    if exc_info:
        exc_info_value = sys.exc_info()
    
    record = logging.LogRecord(
        name=log_obj.name,
        level=log_level,
        pathname=info.filename,
        lineno=info.lineno,
        msg=f"{msg}",
        args=args or None,
        exc_info=exc_info_value,
        func=info.function
    )
    
    extra_dict['service.name'] = settings.SERVICE_NAME
    extra_dict['container.name'] = settings.CONTAINER_NAME
    extra_dict['method_name'] = logging.getLevelName(record.levelno).lower()
    
    # Use helper methods to serialize locals and add stack trace
    extra_dict = _serialize_locals(arg_info, extra_dict, log_level)
    extra_dict = _add_stack_trace(extra_dict, log_level)

    # Add the 'extra' fields to the '__dict__' attribute of the 'LogRecord' object
    for key, value in extra_dict.items():
        record.__dict__[key] = value

    # Create the filter
    debug_filter = DebugFilter()

    # Get the console handlers
    console_handler = getHandlerByName('console', log_obj)

    # Add the filter to the handlers
    if console_handler is not None:
        console_handler.addFilter(debug_filter)
    
    # Handle the record
    log_obj.handle(record)

def format_request(request: Request) -> dict[str, Any]:
    # Example: Exclude 'Cookie' and 'Authorization' headers
    excluded_headers = ['accept-encoding', 'cf-ray', 'cf-warp-tag-id', 'connection', 'x-forwarded-server']


    return {
        "Method": str(request.method),
        "URL": f"{request.headers['host']}{request['path']}",
        "URL-Path": request['path'],
        "Query-Parameters": dict(request.query_params),
        "headers": {k: str(v) for k, v in dict(request.headers).items() if k not in excluded_headers},
        "Client-IP": str(ip_resolver.get_ip(request.headers)),
        "Client-Country": str(request.headers.get("cf-ipcountry", "")),
        "User-Agent": str(request.headers.get("user-agent", "Unknown")),
        "Req-Info": getattr(request.state, "req_info", {}),
    }

class StructlogFormatter(logging.Formatter):
    def __init__(self, processors: list[Any] | None = None, exclude: list[str] | None = None, *args: Any, **kwargs: Any) -> None:
        super().__init__('', *args, **kwargs)  # Pass an empty string as the format string
        if processors is None:
            processors = []
        self.processors = [
            self._import_processor(processor) for processor in processors
        ]
        self.exclude = exclude or []

    def _import_processor(self, processor: Any) -> Any:
        if isinstance(processor, str):
            module_name, class_name = processor.rsplit('.', 1)
            module = importlib.import_module(module_name)
            return getattr(module, class_name)()
        elif isinstance(processor, dict):
            module_name, class_name = processor['class'].rsplit('.', 1)
            module = importlib.import_module(module_name)
            class_ = getattr(module, class_name)
            args = processor.get('args', [])
            kwargs = processor.get('kwargs', {})
            return class_(*args, **kwargs)

    def format(self, record: logging.LogRecord) -> str:
        event_dict: dict[str, Any] = {
            'event': escape_ansi(record.msg),
            'logger': record.name,
            'level': record.levelname,
            'timestamp': record.created,
        }
        # Exclude attributes that are in self.exclude
        extra_dict: dict[str, Any] = {k: v for k, v in record.__dict__.items() if k not in event_dict and k not in self.exclude}
        event_dict.update(extra_dict)
        for processor in self.processors:
            event_dict = processor(None, None, event_dict)
        
        # Convert the dictionary to a JSON string
        return json.dumps(event_dict, cls=LogEncoder, indent=2)


TIME_ORDER_SUFFIXES: list[str] = ["nsec", "μsec", "msec", "sec"]

def magnitude_fmt_time(nanosec: int | float) -> str:
    suffix = None
    for suffix in TIME_ORDER_SUFFIXES:
        if nanosec < 1000:
            break
        nanosec /= 1000
    return f"{nanosec:.2f} {suffix}"

class LogEncoder(json.JSONEncoder):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.currently_processing: set[Any] = set()

    def default(self, o: Any) -> str | dict[Any, str | dict[Any, Any]]:
        if id(o) in self.currently_processing:
            return "Circular reference detected"
        self.currently_processing.add(id(o))

        try:
            if isinstance(o, datetime.datetime):
                return o.isoformat()
            elif isinstance(o, bytes):
                return o.decode('utf-8')
            elif hasattr(o, "__dict__"):
                return {k: self.default(v) for k, v in o.__dict__.items()}
            else:
                return str(o)
        finally:
            # Remove the object from the set of currently processing objects
            self.currently_processing.remove(id(o))

    def encode(self, o: Any) -> str:
        if isinstance(o, dict):
            # Convert keys of type `type` to strings
            o = self._convert_dict(o)
        return super().encode(o)

    def _convert_dict(self, o: dict[Any, Any]) -> dict[str, Any]:
        new_dict: dict[str, Any] = {}
        for k, v in o.items():
            if isinstance(k, type):
                k = str(k)
            if isinstance(v, dict):
                v = self._convert_dict(v)
            else:
                v = self.default(v)
            new_dict[k] = v
        return new_dict

P = ParamSpec("P")
R = TypeVar("R")

def error_catcher(func: Callable[P, R]) -> Callable[P, R]:
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return cast(R, await func(*args, **kwargs))
            except Exception as e:
                # Capture the exception info before doing anything else
                exc_type, exc_value, exc_traceback = sys.exc_info()
                
                log(f"Error in {func.__name__}: {e}", start_color=Ansi.LRED, level=logging.ERROR, extra={
                    "error": f"{e}",
                    "original_traceback": "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
                    "exception_location": traceback.extract_tb(exc_traceback)[-1],  # Last frame is where exception occurred
                    "function_name": func.__name__,
                    "function_module": func.__module__
                })
                # Re-raise the exception to maintain expected behavior
                raise
        return async_wrapper  # type: ignore[return-value]
    else:
        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Capture the exception info before doing anything else
                exc_type, exc_value, exc_traceback = sys.exc_info()
                
                log(f"Error in {func.__name__}: {e}", start_color=Ansi.LRED, level=logging.ERROR, extra={
                    "error": f"{e}",
                    "original_traceback": "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
                    "exception_location": traceback.extract_tb(exc_traceback)[-1],  # Last frame is where exception occurred
                    "function_name": func.__name__,
                    "function_module": func.__module__
                })
                # Re-raise the exception to maintain expected behavior
                raise
        return sync_wrapper
