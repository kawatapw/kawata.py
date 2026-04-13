from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import httpx
import pytest
import respx
import structlog
from asgi_lifespan import LifespanManager
from asgi_lifespan._types import ASGIApp
from fastapi import status
import structlog
import logging

from app.api.init_api import asgi_app

# TODO: fixtures for postgres database connection(s) for itests

# TODO: I believe if we switch to fastapi.TestClient, we
# will no longer need to use the asgi-lifespan dependency.
# (We do not need an asynchronous http client for our tests)


@pytest.fixture(autouse=True)
def mock_out_initial_image_downloads(respx_mock: respx.MockRouter) -> None:
    # mock out default avatar download
    respx_mock.get("https://i.cmyui.xyz/U24XBZw-4wjVME-JaEz3.png").mock(
        return_value=httpx.Response(
            status_code=status.HTTP_200_OK,
            headers={"Content-Type": "image/png"},
            content=b"i am a png file",
        ),
    )
    # mock out achievement image downloads
    respx_mock.get(url__regex=r"https://assets.ppy.sh/medals/client/.+").mock(
        return_value=httpx.Response(
            status_code=status.HTTP_200_OK,
            headers={"Content-Type": "image/png"},
            content=b"i am a png file",
        ),
    )


@pytest.fixture
async def app() -> AsyncIterator[ASGIApp]:
    async with LifespanManager(
        asgi_app,
        startup_timeout=None,
        shutdown_timeout=None,
    ) as manager:
        yield manager.app


@pytest.fixture
async def http_client(app: ASGIApp) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client

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

@pytest.fixture(autouse=True, scope="session")
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
    console_logger = logging.getLogger("console")
    console_logger.setLevel(logging.DEBUG)
    console_logger.addHandler(handler)

    # Ensure the root logger is also set up
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)

    yield

    # Cleanup if necessary


pytest_plugins = []

