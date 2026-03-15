"""
Middlewares Module - HTTP Request/Response Processing Middleware

This module provides HTTP middleware components for the osu! server application,
implementing cross-cutting concerns such as request logging, performance metrics
collection, and error handling. The middleware intercepts all HTTP requests and
responses to provide consistent monitoring and logging across all API endpoints.

The module implements the Starlette middleware pattern, allowing for transparent
processing of requests and responses without modifying the core application logic.
This approach ensures that monitoring and logging capabilities are consistently
applied across all endpoints while maintaining clean separation of concerns.

Key Features:
    - Request/response timing and performance metrics
    - Comprehensive request logging with structured data
    - Response status code monitoring and categorization
    - Error handling for malformed requests
    - Process time header injection for client-side monitoring
    - Color-coded logging based on response status
    - JSON-formatted request/response data for analysis

Integration Points:
    - Logging system in app/logging.py
    - Settings configuration in app/settings.py
    - FastAPI application in app/api/init_api.py
    - All API endpoints through middleware chain

Middleware Behavior:
    - Intercepts all incoming HTTP requests
    - Records request start time using high-precision timer
    - Passes request to next middleware/endpoint
    - Handles TypeError exceptions from malformed requests
    - Calculates request processing time
    - Logs request details with color-coded status
    - Adds process-time header to response
    - Returns response to client

Logging Format:
    - Method: HTTP method (GET, POST, etc.)
    - Status Code: HTTP response status code
    - URL: Full request URL
    - Processing Time: Request duration in human-readable format
    - Color Coding: Green for success (<400), Red for errors (>=400)

Usage Pattern:
    # Middleware is automatically applied to all requests
    # No manual invocation required
    
    # Example log output:
    # [GET] 200 https://osu.example.com/api/v1/players | Request took: 15ms
    
    # Process time header added to response:
    # process-time: 15.234

Related Files:
    - app/api/init_api.py: FastAPI application initialization
    - app/logging.py: Logging utilities and formatting
    - app/settings.py: Application configuration
"""

from __future__ import annotations

import time, json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.logging import Ansi, log, magnitude_fmt_time, format_request
import app.settings


class MetricsMiddleware(BaseHTTPMiddleware):
    """HTTP middleware for request/response metrics and logging.
    
    This middleware intercepts all HTTP requests to provide comprehensive
    logging, performance metrics, and error handling. It measures request
    processing time, logs request details, and adds timing headers to responses.
    
    The middleware handles both successful requests and errors, providing
    consistent monitoring across all API endpoints.
    """
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        start_time = time.perf_counter_ns()
        try:
            response = await call_next(request)
        except TypeError as e:
            # Handle any non JSON serializable requests
            log(
                f"Bad Request | URL: {request.url} | Error: {e}",
                Ansi.LRED,
                extra={
                    "Exception": str(e),
                    "Request-URL": request.url,
                    "Request": json.dumps(format_request(request)),
                    },
                )
            response = Response(content="Internal Server Error: Bad Request", status_code=500)
        end_time = time.perf_counter_ns()

        time_elapsed = end_time - start_time

        col = Ansi.LGREEN if response.status_code < 400 else Ansi.LRED

        url = f"{request.headers['host']}{request['path']}"

        log(
            f"[{request.method}] {response.status_code} {url}{Ansi.RESET!r} | {Ansi.LBLUE!r}Request took: {magnitude_fmt_time(time_elapsed)}",
            col,
            extra={
                "Request": json.dumps(format_request(request)),
                "Response": json.dumps({
                    "Status-Code": str(response.status_code),
                    "Headers": {k: str(v) for k, v in dict(response.headers).items()},
                })
            }
        )

        response.headers["process-time"] = str(round(time_elapsed) / 1e6)
        return response
