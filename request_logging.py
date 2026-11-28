import logging
import re
from uuid import uuid4

from fastapi import FastAPI, Request, Response

REQUEST_ID_HEADER = "X-Request-ID"
logger = logging.getLogger("uvicorn.error")


def add_request_logging(app: FastAPI, service: str, path_prefix: str) -> None:
    @app.middleware("http")
    async def log_request(request: Request, call_next) -> Response:
        path = request.url.path
        if path != path_prefix and not path.startswith(f"{path_prefix}/"):
            return await call_next(request)

        incoming_id = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming_id if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", incoming_id) else uuid4().hex
        request.state.request_id = request_id

        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            logger.info(
                "service=%s request_id=%s method=%s path=%r status=%s",
                service, request_id, request.method, path, status,
            )
