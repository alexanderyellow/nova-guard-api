from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ProblemDetail(BaseModel):
    type: str
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    errors: list[dict[str, Any]] | None = None


class Paginated(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    _links: dict[str, Any] | None = Field(default=None, alias="_links")

    model_config = {"populate_by_name": True}
