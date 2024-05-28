from __future__ import annotations

import time, json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.logging import Ansi
from app.logging import log
from app.logging import magnitude_fmt_time
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
            log(
                f"Bad Request | URL: {request.url} | Error: {e}", 
                Ansi.LRED,
                extra={
                    "Exception": str(e),
                    "Request-URL": request.url,
                    "Request": request,
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
                "Request": json.dumps({
                    "Method": str(request.method),
                    "URL": str(url),
                    "Request-Time": str(magnitude_fmt_time(time_elapsed)),
                    "Query-Parameters": dict(request.query_params),
                    "Headers": {k: str(v) for k, v in dict(request.headers).items()},
                    "Client-IP": str(request.headers.get("cf-connecting-ip", "")),
                    "Client-Country": str(request.headers.get("cf-ipcountry", "")),
                    "User-Agent": str(request.headers.get("user-agent", "Unknown")),
                    "Req-Info": getattr(request.state, "req_info", {}),
                }),
                "Response": json.dumps({
                    "Status-Code": str(response.status_code),
                    "Headers": {k: str(v) for k, v in dict(response.headers).items()},
                })
            }
        )

        response.headers["process-time"] = str(round(time_elapsed) / 1e6)
        return response
