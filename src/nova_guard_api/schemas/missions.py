from pydantic import BaseModel, ConfigDict

from nova_guard_api.db.models import MissionStatus, MissionType


class MissionCreate(BaseModel):
    mission_type: MissionType
    reward_credits: int
    danger_rating: int
    issuer_faction_id: int
    target_planet_id: int
    title: str = ""


class MissionPatch(BaseModel):
    status: MissionStatus | None = None
    title: str | None = None
    squad_id: int | None = None


class MissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    mission_type: str
    status: str
    reward_credits: int
    danger_rating: int
    issuer_faction_id: int
    target_planet_id: int
    squad_id: int | None
    title: str


class MissionAcceptBody(BaseModel):
    squad_id: int


class MissionBulkCreate(BaseModel):
    missions: list[MissionCreate]
