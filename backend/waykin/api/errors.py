"""Error mapping. Every error body is the `Error` model; messages never contain coordinates."""

from __future__ import annotations

import re

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_NUMBERISH = re.compile(r"-?\d+\.\d+")
_STATUS_CODES = {401: "invalid_token", 403: "forbidden", 404: "not_found", 410: "expired", 429: "rate_limited"}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _validation_message(exc: RequestValidationError) -> str:
    parts = []
    for err in exc.errors()[:5]:
        loc = ".".join(_NUMBERISH.sub("?", str(x)) for x in err.get("loc", ()))
        parts.append(f"{loc} ({err.get('type', 'invalid')})")
    return "Invalid request: " + "; ".join(parts) if parts else "Invalid request."


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(422, "validation", _validation_message(exc))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "validation")
        msg = exc.detail if isinstance(exc.detail, str) and not _NUMBERISH.search(exc.detail) else "Request failed."
        return error_response(exc.status_code, code, msg)
