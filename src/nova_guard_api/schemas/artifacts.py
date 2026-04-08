from pydantic import BaseModel, ConfigDict

from nova_guard_api.db.models import ArtifactRarity, LegalStatus


class ArtifactCreate(BaseModel):
    name: str
    origin_planet_id: int
    rarity: ArtifactRarity
    power_description: str
    legal_status: LegalStatus
    holder_character_id: int | None = None
    holder_faction_id: int | None = None


class ArtifactUpdate(BaseModel):
    name: str | None = None
    origin_planet_id: int | None = None
    rarity: ArtifactRarity | None = None
    power_description: str | None = None
    legal_status: LegalStatus | None = None
    holder_character_id: int | None = None
    holder_faction_id: int | None = None


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    name: str
    origin_planet_id: int
    rarity: str
    power_description: str
    legal_status: str
    holder_character_id: int | None
    holder_faction_id: int | None


class ArtifactTransfer(BaseModel):
    holder_character_id: int | None = None
    holder_faction_id: int | None = None


class InfinityTransferAccepted(BaseModel):
    job_id: int
    status: str
    message: str
