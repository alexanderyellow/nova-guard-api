from pydantic import BaseModel, ConfigDict

from nova_guard_api.db.models import Alignment


class FactionCreate(BaseModel):
    name: str
    alignment: Alignment
    is_nova_guard: bool = False


class FactionUpdate(BaseModel):
    name: str | None = None
    alignment: Alignment | None = None
    is_nova_guard: bool | None = None


class FactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    name: str
    alignment: str
    is_nova_guard: bool
