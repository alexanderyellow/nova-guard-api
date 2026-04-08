"""RFC 9457 Problem Details."""

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def problem(
    *,
    type_: str,
    title: str,
    status_code: int,
    detail: str | None = None,
    instance: str | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": type_,
        "title": title,
        "status": status_code,
    }
    if detail is not None:
        body["detail"] = detail
    if instance is not None:
        body["instance"] = instance
    if errors:
        body["errors"] = errors
    return body


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errs = []
    for e in exc.errors():
        errs.append({"loc": list(e.get("loc", ())), "msg": e.get("msg", ""), "type": e.get("type", "")})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=problem(
            type_="https://nova-guard.dev/problems/validation-error",
            title="Validation Error",
            status_code=422,
            detail="Request validation failed",
            instance=str(request.url),
            errors=errs,
        ),
        media_type="application/problem+json",
    )


class ProblemError(Exception):
    def __init__(
        self,
        status_code: int,
        *,
        type_: str,
        title: str,
        detail: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.type_ = type_
        self.title = title
        self.detail = detail


async def problem_error_handler(request: Request, exc: ProblemError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=problem(
            type_=exc.type_,
            title=exc.title,
            status_code=exc.status_code,
            detail=exc.detail,
            instance=str(request.url),
        ),
        media_type="application/problem+json",
    )
