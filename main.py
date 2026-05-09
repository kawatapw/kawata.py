"""
Main Application Entry Point - Server Startup and Configuration

This module serves as the main entry point for the osu! server application,
initializing the FastAPI/Starlette ASGI server and configuring all necessary
components for the bancho.py server to operate. It handles logging setup,
displays startup information, and launches the uvicorn ASGI server with
appropriate configuration settings.

The module is designed to be executed directly as a Python script, providing
a clean startup sequence that initializes all required services and begins
listening for incoming connections on the configured host and port.

Key Features:
    - ASGI server initialization using uvicorn
    - Logging system configuration
    - Startup dialog display with server information
    - Configurable host and port binding
    - Debug mode support with auto-reload
    - Custom HTTP headers for version identification
    - Clean shutdown handling

Integration Points:
    - FastAPI application in app/api/init_api.py
    - Settings configuration in app/settings.py
    - Logging setup in app/logging.py
    - Utility functions in app/utils.py
    - Server configuration via environment variables

Server Configuration:
    - Host: Configured via APP_HOST environment variable
    - Port: Configured via APP_PORT environment variable
    - Debug mode: Enabled via DEBUG_LEVEL >= 1
    - Auto-reload: Enabled in debug mode for development
    - Custom headers: bancho-version header with server version

Usage Pattern:
    # Run the server directly
    python main.py

    # Or run with uvicorn command
    uvicorn app.api.init_api:asgi_app --host 0.0.0.0 --port 8000

    # Debug mode with auto-reload
    DEBUG_LEVEL=1 python main.py

Related Files:
    - app/api/init_api.py: FastAPI application initialization
    - app/settings.py: Server configuration settings
    - app/logging.py: Logging configuration
    - app/utils.py: Utility functions including startup dialog
"""

#!/usr/bin/env python3.11
from __future__ import annotations

import logging
import sys

import uvicorn

import app.logging
import app.settings
import app.utils

app.logging.configure_logging()


def main() -> int:
    """Main entry point for the osu! server application.

    This function initializes the server, displays startup information,
    and launches the uvicorn ASGI server with the configured settings.

    Returns:
        int: Exit code (0 for success)
    """
    app.utils.display_startup_dialog()
    uvicorn.run(
        "app.api.init_api:asgi_app",
        reload=app.settings.DEBUG_LEVEL >= 1,
        log_level=logging.WARNING,
        server_header=False,
        date_header=False,
        headers=[("bancho-version", app.settings.VERSION)],
        host=app.settings.APP_HOST,
        port=app.settings.APP_PORT,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
