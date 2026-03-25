"""
Utility Functions Module - Common Utilities and Helper Functions

This module provides a comprehensive collection of utility functions and helper
methods used throughout the osu! server application. It includes functions for
file handling, network operations, debugging, logging, and various other
common operations that support the core functionality of the server.

The module serves as a central repository for shared functionality, reducing
code duplication and providing consistent implementations of common operations.
It includes utilities for achievement image downloading, network connectivity
checking, stack trace analysis, and various debugging and logging helpers.

Key Features:
    - Achievement image downloading from osu! servers
    - Network connectivity checking
    - Stack trace analysis and formatting
    - Debug level monitoring and adjustment
    - File type detection (JPEG, PNG)
    - Request data extraction utilities
    - Database encoding helpers
    - Startup dialog and system checks
    - Persistent volume management

Integration Points:
    - Achievement system in app/usecases/achievements.py
    - Logging system in app/logging.py
    - Settings configuration in app/settings.py
    - Database operations in app/adapters/database.py
    - API request handling in app/api/
    - File system operations throughout the application

Utility Categories:
    - File Operations: Achievement downloads, avatar management
    - Network Utilities: Connectivity checking, HTTP requests
    - Debug Utilities: Stack traces, debug level management
    - Request Utilities: Form data, body, and file extraction
    - Database Utilities: Encoding helpers for MySQL
    - System Utilities: Admin checks, startup dialogs

Usage Pattern:
    # Download achievement images
    download_achievement_images(achievements_path)

    # Check internet connectivity
    if has_internet_connectivity():
        # Perform online operations
        pass

    # Get stack trace for debugging
    stack_info = get_appropriate_stacktrace()

    # Extract request data
    form_data = await get_form_data("SCORE", request)
    body = await get_request_body("SCORE", request)
    files = await get_request_files("SCORE", request)

Related Files:
    - app/logging.py: Logging utilities and formatters
    - app/settings.py: Configuration settings
    - app/api/: API request handling
    - app/usecases/achievements.py: Achievement processing
    - app/adapters/database.py: Database operations
"""

from __future__ import annotations

import asyncio
import ctypes
import inspect
import json
import logging
import os
import socket
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, TypeVar

import httpx
import pymysql
from fastapi.datastructures import FormData
from starlette.requests import Request

import app.settings
from app.logging import Ansi, format_request, log, logLevel

if TYPE_CHECKING:
    pass

T = TypeVar("T")


DATA_PATH = Path.cwd() / ".data"
ACHIEVEMENTS_ASSETS_PATH = DATA_PATH / "assets/medals/client"
DEFAULT_AVATAR_PATH = DATA_PATH / "avatars/default.jpg"


def make_safe_name(name: str) -> str:
    """Return a name safe for usage in sql."""
    return name.lower().replace(" ", "_")


def _download_achievement_images_osu(achievements_path: Path) -> bool:
    """Download all used achievement images (one by one, from osu!)."""
    achs: list[str] = []

    for resolution in ("", "@2x"):
        for mode in ("osu", "taiko", "fruits", "mania"):
            # only osu!std has 9 & 10 star pass/fc medals.
            for star_rating in range(1, 1 + (10 if mode == "osu" else 8)):
                achs.append(f"{mode}-skill-pass-{star_rating}{resolution}.png")
                achs.append(f"{mode}-skill-fc-{star_rating}{resolution}.png")

        for combo in (500, 750, 1000, 2000):
            achs.append(f"osu-combo-{combo}{resolution}.png")

        for mod in (
            "suddendeath",
            "hidden",
            "perfect",
            "hardrock",
            "doubletime",
            "flashlight",
            "easy",
            "nofail",
            "nightcore",
            "halftime",
            "spunout",
        ):
            achs.append(f"all-intro-{mod}{resolution}.png")

    log("Downloading achievement images from osu!.", Ansi.LCYAN)

    for ach in achs:
        resp = httpx.get(f"https://assets.ppy.sh/medals/client/{ach}")
        if resp.status_code != 200:
            return False

        log(f"Saving achievement: {ach}", Ansi.LCYAN)
        (achievements_path / ach).write_bytes(resp.content)

    return True


def download_achievement_images(achievements_path: Path) -> None:
    """Download all used achievement images (using the best available source)."""

    # download individual files from the official osu! servers
    downloaded = _download_achievement_images_osu(achievements_path)

    if downloaded:
        log("Downloaded all achievement images.", Ansi.LGREEN)
    else:
        # TODO: make the code safe in this state
        log("Failed to download achievement images.", Ansi.LRED)
        achievements_path.rmdir()

        # allow passthrough (don't hard crash).
        # the server will *mostly* work in this state.
        pass


def download_default_avatar(default_avatar_path: Path) -> None:
    """Download an avatar to use as the server's default."""
    resp = httpx.get("https://i.cmyui.xyz/U24XBZw-4wjVME-JaEz3.png")

    if resp.status_code != 200:
        log("Failed to fetch default avatar.", Ansi.LRED)
        return

    log("Downloaded default avatar.", Ansi.LGREEN)
    default_avatar_path.write_bytes(resp.content)


def has_internet_connectivity(timeout: float = 1.0) -> bool:
    """Check for an active internet connection."""
    COMMON_DNS_SERVERS = (
        # Cloudflare
        "1.1.1.1",
        "1.0.0.1",
        # Google
        "8.8.8.8",
        "8.8.4.4",
    )
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        for host in COMMON_DNS_SERVERS:
            try:
                client.connect((host, 53))
            except OSError:
                continue
            else:
                return True

    # all connections failed
    return False


class FrameInfo(TypedDict):
    function: str
    filename: str
    lineno: int
    charno: int
    locals: dict[str, str]


def get_appropriate_stacktrace() -> list[FrameInfo]:
    """Return information of all frames related to cmyui_pkg and below."""
    stack = inspect.stack()[1:]
    for _, frame in enumerate(stack):
        if frame.function == "run":
            break
    else:
        raise Exception

    return [
        {
            "function": frame.function,
            "filename": Path(frame.filename).name,
            "lineno": frame.lineno,
            "charno": frame.index or 0,
            "locals": {k: repr(v) for k, v in frame.frame.f_locals.items()},
        }
        # reverse for python-like stacktrace
        # ordering; puts the most recent
        # call closest to the command line
        for frame in reversed(stack[:_])
    ]


def pymysql_encode(
    conv: Callable[[Any, dict[object, object] | None], str],
) -> Callable[[type[T]], type[T]]:
    """Decorator to allow for adding to pymysql's encoders."""

    def wrapper(cls: type[T]) -> type[T]:
        pymysql.converters.encoders[cls] = conv
        return cls

    return wrapper


def escape_enum(
    val: Any,
    _: dict[object, object] | None = None,
) -> str:  # used for ^
    return str(int(val))


def ensure_persistent_volumes_are_available() -> None:
    # create /.data directory
    DATA_PATH.mkdir(exist_ok=True)

    # create /.data/... subdirectories
    for sub_dir in ("avatars", "logs", "osu", "osr", "ss"):
        subdir = DATA_PATH / sub_dir
        subdir.mkdir(exist_ok=True)

    # download achievement images from osu!
    if not ACHIEVEMENTS_ASSETS_PATH.exists():
        ACHIEVEMENTS_ASSETS_PATH.mkdir(parents=True)
        download_achievement_images(ACHIEVEMENTS_ASSETS_PATH)

    # download a default avatar image for new users
    if not DEFAULT_AVATAR_PATH.exists():
        download_default_avatar(DEFAULT_AVATAR_PATH)


def is_running_as_admin() -> bool:
    try:
        return os.geteuid() == 0  # type: ignore[attr-defined, no-any-return, unused-ignore]
    except AttributeError:
        pass

    try:
        return ctypes.windll.shell32.IsUserAnAdmin() == 1  # type: ignore[attr-defined, no-any-return, unused-ignore]
    except AttributeError:
        raise Exception(
            f"{sys.platform} is not currently supported on bancho.py, please create a github issue!",
        ) from None


def display_startup_dialog() -> None:
    """Print any general information or warnings to the console."""
    if app.settings.DEVELOPER_MODE:
        log("running in advanced mode", Ansi.LYELLOW)
    log(
        f"running in debug mode at level {app.settings.DEBUG_LEVEL}",
        Ansi.LMAGENTA,
        extra={
            "filter": {
                "debugLevel": 1,
            },
        },
    )
    log(
        f"current debug focus: {app.settings.DEBUG_FOCUS}",
        Ansi.LMAGENTA,
        extra={
            "filter": {
                "debugLevel": 1,
            },
        },
    )

    # running on root/admin grants the software potentally dangerous and
    # unnecessary power over the operating system and is not advised.
    if is_running_as_admin():
        log(
            "It is not recommended to run bancho.py as root/admin, especially in production."
            + (
                " You are at increased risk as developer mode is enabled."
                if app.settings.DEVELOPER_MODE
                else ""
            ),
            Ansi.LYELLOW,
        )

    if not has_internet_connectivity():
        log("No internet connectivity detected", Ansi.LYELLOW)


def has_jpeg_headers_and_trailers(data_view: memoryview) -> bool:
    return data_view[:4] == b"\xff\xd8\xff\xe0" and data_view[6:11] == b"JFIF\x00"


def has_png_headers_and_trailers(data_view: memoryview) -> bool:
    return (
        data_view[:8] == b"\x89PNG\r\n\x1a\n"
        and data_view[-8:] == b"\x49END\xae\x42\x60\x82"
    )


async def get_form_data(type: str, request: Request) -> FormData | None:
    try:
        return await request.form()
    except Exception:
        # Handle the exception here
        log(
            "Request has no Form Data",
            Ansi.GRAY,
            extra={
                "filter": {"debugLevel": 2, "debugFocus": "requests"},
            },
            level=14,
            logger="console.debug",
        )
        return None


async def get_request_body(type: str, request: Request) -> bytes | None:
    try:
        request._body = await request.body()
        log(
            f"Request Body: {request._body!r}",
            Ansi.GRAY,
            level=16,
            logger="console.debug.requests",
            extra={
                "filter": {"debugLevel": 1, "debugFocus": "requests"},
            },
        )
        return request._body
    except Exception as e:
        # Handle the exception here
        log(
            "Request has no Body",
            Ansi.GRAY,
            extra={
                "filter": {"debugLevel": 2, "debugFocus": "requests"},
                "Error": e,
                "Request": json.dumps(format_request(request)),
            },
            level=30,
            logger="console.debug.requests",
        )
        return None


async def get_request_files(type: str, request: Request) -> dict[str, Any] | None:
    try:
        form_data = await request.form()
        # Extract files from form data
        files: dict[str, Any] = {}
        for key, value in form_data.items():
            if hasattr(value, "filename"):  # It's a file
                files[key] = value
        return files if files else None
    except Exception as e:
        # Handle the exception here
        log(
            "Request Contains no Files",
            Ansi.GRAY,
            level=40,
            extra={
                "filter": {"debugLevel": 2, "debugFocus": "requests"},
                "Error": e,
                "Request": json.dumps(format_request(request)),
            },
        )
        return None


async def write_log_file(type: str, file_path: str, request: Request) -> None:
    log(
        "Writing Log File for Old Client Submission",
        Ansi.GRAY,
        level=16,
        logger="console.debug",
    )
    with open(file_path, "w") as file:
        if type == "SCORE":
            file.write("Old Client Score Submission:\n")
        file.write("Request Headers:\n")
        for header, value in request.headers.items():
            file.write(f"{header}: {value}\n")
        log("Request headers written, Grabbing Form_Data Next", Ansi.GRAY)
        form_data = await get_form_data(type, request)
        log("Grabbed Form Data", Ansi.GRAY)
        if form_data is not None:
            # Extract the aliases and their values from the form data
            aliases = {alias: str(form_data.get(alias)) for alias in form_data}
            # Convert the aliases dictionary to JSON format
            aliases_json = json.dumps(aliases, indent=4)
            file.write("Request Forms: \n")
            file.write(aliases_json)
            log("Form Data Written")
        # Read the request body as bytes and decode it
        body = await get_request_body(type, request)
        if body is not None:
            try:
                body_str = body.decode()
            except Exception:
                body_str = None
            file.write("\nRequest Body:\n")
            # ...existing code...
            file.write(body_str if body_str is not None else "Unable to decode body")
        files = await get_request_files(type, request)
        if files is not None:
            file.write("\nFiles:\n")
            for field, uploaded_file in files.items():
                file.write(f"{field}: {uploaded_file.filename}\n")
        if type == "SCORE":
            log("Log File for Old Client Submission written successfully", Ansi.GRAY)


class DebugLevelWatcher:
    @staticmethod
    async def watch(interval: int) -> None:
        """Watch app.settings.DEBUG_LEVEL for changes and execute something on change."""
        current_debug_level = app.settings.DEBUG_LEVEL
        DebugLevelWatcher.set_debug_level()

        while True:
            if app.settings.DEBUG_LEVEL != current_debug_level:
                # DEBUG_LEVEL has changed, execute something
                DebugLevelWatcher.set_debug_level()

                # Update current_debug_level
                current_debug_level = app.settings.DEBUG_LEVEL

            # Sleep for a short interval before checking again
            await asyncio.sleep(interval)

    @staticmethod
    def set_debug_level() -> None:
        """Set debug level stuff."""
        DebugLevelWatcher.loggerLevel()

    @staticmethod
    def loggerLevel() -> None:
        """Set debug level stuff."""

        try:
            console_logger = logging.getLogger("console")
            console_handlers = console_logger.handlers
            for handler in console_handlers:
                # Sets Console Logger Level based on current DebugLevel
                if app.settings.DEBUG_LEVEL == 3:
                    handler.setLevel(logLevel.VERBOSE)
                elif app.settings.DEBUG_LEVEL == 2:
                    handler.setLevel(logLevel.DBGLV2)
                elif app.settings.DEBUG_LEVEL == 1:
                    handler.setLevel(logLevel.DBGLV1)
                elif app.settings.DEBUG_LEVEL == 0:
                    handler.setLevel(logLevel.INFO)
                else:
                    handler.setLevel(logLevel.DEBUG)
            pass
        except Exception as e:
            log(
                f"Failed to set logger level: {e}",
                Ansi.LRED,
                extra={
                    "message": "Failed to set logger level. Check the error message for more information.",
                    "error": str(e),
                    "traceback": f"{e.__traceback__}",
                },
            )
            pass
