from __future__ import annotations

from datetime import datetime
import logging.config
from logging.handlers import HTTPHandler
import re
from collections.abc import Mapping
from enum import IntEnum
from zoneinfo import ZoneInfo

import yaml, os
import json, jsons
import orjson, rapidjson
from app import settings
import structlog
from structlog.stdlib import NAME_TO_LEVEL
import importlib
import datetime
import inspect
from pythonjsonlogger import jsonlogger
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import SerializationError
from logging import Handler
import traceback, sys
import time

# Stupid Dumb Fucking Json Serialization BS IMPORTS OMFG I'M LOSING MY MIND
import decimal
from ipaddress import IPv4Network, IPv4Address

def ipv4network_serializer(obj: IPv4Network, **kwargs):
    return str(obj)

def ipv4address_serializer(obj: IPv4Address, **kwargs):
    return str(obj)

jsons.set_serializer(ipv4network_serializer, IPv4Network)
jsons.set_serializer(ipv4address_serializer, IPv4Address)

def setup_logging(default_path='logging.yaml', default_level=logging.INFO, env_key='LOG_CFG'):
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

def setup_structlog():
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

def configure_logging():
    setup_logging()
    setup_structlog()

class ElasticsearchHandler(Handler):
    def __init__(self, hosts, index, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.es = Elasticsearch(hosts)
        logging.getLogger('elasticsearch').setLevel(logging.WARNING)
        self.index = index

    def emit(self, record):
        # Remove the logger key
        record_dict = record.__dict__
        if 'logger' in record_dict:
            del record_dict['logger']
        
        try:
            serializable_record = serialize_record(record)
        except Exception as e:
            log(f"Failed to serialize record: {e}", start_color=Ansi.LRED, level=logging.WARNING, extra={
                'CodeRegion': 'Logging', "Func": "ElasticsearchHandler.emit",
                "message": f"Failed to serialize record: {e}",
                "error": f"{e}",
                "traceback": traceback.format_exc(),
                "record": str(record_dict),
                })
            serializable_record = {
                "message": f"Failed to serialize record: {e}",
                "error": f"{e}",
                "traceback": traceback.format_exc(),
                "record": str(record_dict),
                }
        self.es.index(index=self.index, body=serializable_record)


def serialize_record(record, seen=None):
    if seen is None:
        seen = set()
    seen.add(id(record))

    def serialize(value):
        try:
            if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
                return value.isoformat()
            elif isinstance(value, decimal.Decimal):
                return float(value)
            elif isinstance(value, bytes):
                return value.decode('utf-8')
            elif isinstance(value, (list, set, tuple)):
                return [serialize(item) for item in value]
            elif isinstance(value, dict):
                return {key: serialize(val) for key, val in value.items()}
            elif hasattr(value, '__dict__'):
                if id(value) in seen:
                    return f"<Circular Reference: {type(value).__name__} id={id(value)}>"
                else:
                    return serialize_record(value, seen)
        except:
            pass
        try:
            json_record = json.dumps(value)
            return json_record
        except:
            try:
                # Try to serialize with orjson
                serialized_record = orjson.dumps(value).decode()
                return serialized_record
            except:
                try:
                    # Try to serialize with jsons
                    serialized_record = jsons.dumps(value)
                    return serialized_record
                except:
                    try:
                        # Try to serialize with rapidjson
                        serialized_record = rapidjson.dumps(value)
                        return serialized_record
                    except:
                        return str(value)

    serializable_record = {}
    for key, value in record.__dict__.items():
        serializable_record[key] = serialize(value)

    return serializable_record

class BytesJsonFormatter(jsonlogger.JsonFormatter):
    def format(self, record):
        # Convert only keys and values that are not of type str, int, float, bool, or None
        record.__dict__ = {
            str(k) if not isinstance(k, (str, int, float, bool, type(None))) else k:
            str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
            for k, v in record.__dict__.items()
        }

        # Check if the message contains any placeholders as this throws an error when formatting on string_record
        if not re.search(r'%\(.+?\)s', record.msg) and record.args:
            record.args = None

        string_record = super().format(record)
        return string_record.encode('utf-8') + b'\n'


console_logger = logging.getLogger('console')
console_handlers = console_logger.handlers

def get_timestamp(full: bool = False, tz: ZoneInfo | None = None) -> str:
    fmt = "%d/%m/%Y %I:%M:%S%p" if full else "%I:%M:%S%p"
    return f"{datetime.datetime.now(tz=tz):{fmt}}"

def fromtimestamp(timestamp):
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
    def add_Log_Levels(cls):
        logging.addLevelName(cls.VERBOSE, 'VERBOSE')
        logging.addLevelName(cls.DBGLV2, 'DBGLV2')
        logging.addLevelName(cls.DBGLV1, 'DBGLV1')
        # Add the custom log levels to the NAME_TO_LEVEL dictionary in structlog
        NAME_TO_LEVEL['verbose'] = cls.VERBOSE
        NAME_TO_LEVEL['dbglv2'] = cls.DBGLV2
        NAME_TO_LEVEL['dbglv1'] = cls.DBGLV1
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
    exc_info: bool = False,
    *args
) -> None:
    """\
    A thin wrapper around the stdlib logging module to handle mostly
    backwards-compatibility for colours during our migration to the
    standard library logging module.
    """

    # Get the logger
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
    
    # Add Timestamp and Message to the 'extra' fields
    extra = extra or {}
    
    extra['@timestamp'] = datetime.datetime.now().isoformat()
    extra['message'] = msg
    
    # Check if the message contains any placeholders
    if not re.search(r'%\(.+?\)s', msg) and args:
        # If it doesn't, and there are arguments, store the arguments in the 'extra' dict
        if extra is not None:
            extra.update({'extra_args': args})
        else:
            extra = {'extra_args': args}
        args = ()

    # Get the arguments of the calling function
    arg_info = inspect.getargvalues(frame)
    
    msg = f"{color_prefix}{msg}{color_suffix}"

    
    # Create a LogRecord with the correct information
    record = logging.LogRecord(
        name=log_obj.name,
        level=log_level,
        pathname=info.filename,
        lineno=info.lineno,
        msg=f"{msg}",
        args=args or None,
        exc_info=exc_info,
        func=info.function
    )
    
    # Add the logger and methodname to the 'extra' fields
    extra['logger'] = log_obj
    extra['method_name'] = logging.getLevelName(record.levelno).lower()
    extra['service.name'] = settings.SERVICE_NAME
    extra['container.name'] = settings.CONTAINER_NAME
    
    
    if log_level >= 21:
        # Add calling function's arguments to the 'extra' fields
        extra['args'] = arg_info.args
        extra['varargs'] = arg_info.varargs
        extra['keywords'] = arg_info.keywords
        extra['locals'] = arg_info.locals
        extra['func'] = info.function
        # Add stack trace to the 'extra' fields
        extra['stack_trace'] = traceback.format_stack()
        extra['stack'] = inspect.stack()
        
        if log_level >= 40:
            # Add the 'exc_info' to the 'extra' fields
            extra['verbose_stacktrace'] = {}
            if info.function in frame.f_globals:
                extra['verbose_stacktrace']['func_signature'] = str(inspect.signature(frame.f_globals[info.function]))
                extra['verbose_stacktrace']['func_source'] = inspect.getsource(frame.f_globals[info.function])
            extra['verbose_stacktrace']['exc_info'] = exc_info
            extra['verbose_stacktrace']['exc_info'] = traceback.format_exc()
            extra['verbose_stacktrace']['exc_text'] = traceback.format_exc()
            extra['verbose_stacktrace']['exc_type'] = sys.exc_info()[0]
            extra['verbose_stacktrace']['exc_value'] = sys.exc_info()[1]
            extra['verbose_stacktrace']['exception'] = traceback.format_exception(*sys.exc_info())
            extra['verbose_stacktrace']['exception_only'] = traceback.format_exception_only(sys.exc_info()[0], sys.exc_info()[1])
            extra['verbose_stacktrace']['exception_info'] = traceback.format_exception(*sys.exc_info())
            extra['verbose_stacktrace']['exception_text'] = traceback.format_exception(*sys.exc_info())
            extra['verbose_stacktrace']['error'] = sys.exc_info()[1]
            extra['verbose_stacktrace']['error_info'] = traceback.format_exception(*sys.exc_info())
            extra['verbose_stacktrace']['error_text'] = traceback.format_exception(*sys.exc_info())
            extra['verbose_stacktrace']['error_message'] = sys.exc_info()[1]
            extra['verbose_stacktrace']['error_type'] = sys.exc_info()[0]
            extra['verbose_stacktrace']['error_traceback'] = traceback.format_exc()
            extra['verbose_stacktrace']['error_stack'] = inspect.stack()
            extra['verbose_stacktrace']['error_locals'] = arg_info.locals
            extra['verbose_stacktrace']['error_args'] = arg_info.args
            extra['verbose_stacktrace']['error_varargs'] = arg_info.varargs
            extra['verbose_stacktrace']['error_keywords'] = arg_info.keywords
            extra['verbose_stacktrace']['error_message'] = msg
            extra['verbose_stacktrace']['error_level'] = log_level
    
    # Add the 'extra' fields to the '__dict__' attribute of the 'LogRecord' object
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