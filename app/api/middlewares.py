from __future__ import annotations

import time
import asyncio
import starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.websockets import WebSocketDisconnect


from app.logging import Ansi
from app.logging import log
from app.logging import magnitude_fmt_time
from app.logging import printc
import app.settings


class MetricsMiddleware(BaseHTTPMiddleware):
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
            log(f"Non JSON Serializable Request | URL: {request.url} | Query Parameters: {request.query_params}", Ansi.YELLOW)
            response = Response(content="Internal Server Error: Non JSON Serializable Request", status_code=500) 
        end_time = time.perf_counter_ns()

        time_elapsed = end_time - start_time

        # TODO: add metric to datadog

        col = (
            Ansi.LGREEN
            if 200 <= response.status_code < 300
            else Ansi.LYELLOW
            if 300 <= response.status_code < 400
            else Ansi.LRED
        )

        url = f"{request.headers['host']}{request['path']}"
        if response.status_code != 307:
            log(f"[{request.method}] {response.status_code} {url}", col, end=" | ")
            printc(f"Request took: {magnitude_fmt_time(time_elapsed)}", Ansi.LBLUE)
            if app.settings.DEBUG and app.settings.DEBUG_REQUESTS:
                    log(f"Request Information | Client IP: {request.headers['cf-connecting-ip']} | Client Country: {request.headers['cf-ipcountry']} | Client User Agent: {request.headers['user-agent']} | Query Parameters: {request.query_params}", Ansi.YELLOW)
                        
        response.headers["process-time"] = str(round(time_elapsed) / 1e6)
        return response
