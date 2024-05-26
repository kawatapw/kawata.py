from __future__ import annotations

import datetime
import logging.config
from logging.handlers import HTTPHandler
import re
from collections.abc import Mapping
from enum import IntEnum
from zoneinfo import ZoneInfo

import yaml
import json
from app import settings
import structlog
import importlib
import datetime
import inspect
from pythonjsonlogger import jsonlogger
from elasticsearch import Elasticsearch
from logging import Handler

class ElasticsearchHandler(Handler):
    def __init__(self, hosts, index, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.es = Elasticsearch(hosts)
        self.index = index

    def emit(self, record):
        self.es.index(index=self.index, body=record.__dict__)
class BytesJsonFormatter(jsonlogger.JsonFormatter):
    def format(self, record):
        string_record = super().format(record)
        return string_record.encode('utf-8') + b'\n'

logconfig = yaml.safe_load(open("logging.yaml").read())
def configure_logging() -> None:
    with open("logging.yaml") as f:
        config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)

console_logger = logging.getLogger('console')
console_handlers = console_logger.handlers

def get_timestamp(full: bool = False, tz: ZoneInfo | None = None) -> str:
    fmt = "%d/%m/%Y %I:%M:%S%p" if full else "%I:%M:%S%p"
    return f"{datetime.datetime.now(tz=tz):{fmt}}"

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
    def add_Log_Levels(cls):
        logging.addLevelName(cls.VERBOSE, 'VERBOSE')
        logging.addLevelName(cls.DBGLV2, 'DBGLV2')
        logging.addLevelName(cls.DBGLV1, 'DBGLV1')
logLevel.add_Log_Levels()

class DebugFilter(logging.Filter):
    def filter(self, record):
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

def getHandlerByName(name, logger):
    for handler in logger.handlers:
        if handler.get_name() == name:
            return handler
    return None


ROOT_LOGGER = logging.getLogger()


def log(
    msg: str,
    start_color: Ansi | None = None,
    extra: Mapping[str, object] | None = None,
    logger: str = '',
    level: int = logging.INFO,
    exc_info: bool = False
) -> None:
    """\
    A thin wrapper around the stdlib logging module to handle mostly
    backwards-compatibility for colours during our migration to the
    standard library logging module.
    """

    # Get the logger
    if logger:
        log_obj = logging.getLogger(logger)
    else:
        if start_color is Ansi.LYELLOW:
            log_obj = logging.getLogger('console.warn')
        elif start_color is Ansi.LRED:
            log_obj = logging.getLogger('console.error')
        else:
            if level:
                if level <= 19:
                    log_obj = logging.getLogger('console.debug')
                else:
                    log_obj = logging.getLogger('console.info')
            else:
                log_obj = logging.getLogger('console.info')

    if level == logging.INFO:
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
    frame = inspect.currentframe().f_back
    info = inspect.getframeinfo(frame)

    # Create a LogRecord with the correct information
    record = logging.LogRecord(
        name=log_obj.name,
        level=log_level,
        pathname=info.filename,
        lineno=info.lineno,
        msg=f"{color_prefix}{msg}{color_suffix}",
        args=None,
        exc_info=exc_info,
        func=info.function
    )
    
    # Add the 'extra' fields to the '__dict__' attribute of the 'LogRecord' object
    if extra is not None:
        for key, value in extra.items():
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

class StructlogFormatter(logging.Formatter):
    def __init__(self, processors=None, exclude=None, *args, **kwargs):
        super().__init__('', *args, **kwargs)  # Pass an empty string as the format string
        if processors is None:
            processors = []
        self.processors = [
            self._import_processor(processor) for processor in processors
        ]
        self.exclude = exclude or []

    def _import_processor(self, processor):
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

    def format(self, record):
        event_dict = {
            'event': escape_ansi(record.msg),
            'logger': record.name,
            'level': record.levelname,
            'timestamp': record.created,
        }
        # Exclude attributes that are in self.exclude
        extra_dict = {k: v for k, v in record.__dict__.items() if k not in event_dict and k not in self.exclude}
        event_dict.update(extra_dict)
        for processor in self.processors:
            event_dict = processor(None, None, event_dict)
        
        # Convert the dictionary to a JSON string
        return json.dumps(event_dict, cls=LogEncoder, indent=2)


TIME_ORDER_SUFFIXES = ["nsec", "μsec", "msec", "sec"]

def magnitude_fmt_time(nanosec: int | float) -> str:
    suffix = None
    for suffix in TIME_ORDER_SUFFIXES:
        if nanosec < 1000:
            break
        nanosec /= 1000
    return f"{nanosec:.2f} {suffix}"

class LogEncoder(json.JSONEncoder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.currently_processing = set()

    def default(self, o):
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

    def encode(self, o):
        if isinstance(o, dict):
            # Convert keys of type `type` to strings
            o = self._convert_dict(o)
        return super().encode(o)

    def _convert_dict(self, o):
        new_dict = {}
        for k, v in o.items():
            if isinstance(k, type):
                k = str(k)
            if isinstance(v, dict):
                v = self._convert_dict(v)
            else:
                v = self.default(v)
            new_dict[k] = v
        return new_dict