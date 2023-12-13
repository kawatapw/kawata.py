#!/usr/bin/env python3.11
"""main.py - a user-friendly, safe wrapper around bancho.py's runtime

bancho.py is an in-progress osu! server implementation for developers of all levels
of experience interested in hosting their own osu private server instance(s).

the project is developed primarily by the Akatsuki (https://akatsuki.pw) team,
and our aim is to create the most easily maintainable, reliable, and feature-rich
osu! server implementation available.

we're also fully open source!
https://github.com/kawatapw/kawata.py
"""
from __future__ import annotations

import logging

import uvicorn

import app.settings
import app.utils


def main() -> int:
    app.utils.display_startup_dialog()
    uvicorn.run(
        "app.api.init_api:asgi_app",
        reload=app.settings.DEBUG,
        log_level=logging.WARNING,
        server_header=False,
        date_header=False,
        headers=[("bancho-version", app.settings.VERSION)],
        host=app.settings.APP_HOST,
        port=app.settings.APP_PORT,
    )
    return 0


if __name__ == "__main__":
    exit(main())
