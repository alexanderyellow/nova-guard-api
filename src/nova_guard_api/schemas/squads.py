from pydantic import BaseModel, ConfigDict

from nova_guard_api.db.models import ShipClass


class SquadCreate(BaseModel):
    captain_character_id: int
    ship_name: str
    ship_class: ShipClass
    reputation: float = 50.0


class SquadPatch(BaseModel):
    ship_name: str | None = None
    ship_class: ShipClass | None = None
    reputation: float | None = None


class SquadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    captain_character_id: int
    ship_name: str
    ship_class: str
    reputation: float


class SquadMemberAdd(BaseModel):
    character_id: int
