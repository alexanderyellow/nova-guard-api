from datetime import datetime

from pydantic import BaseModel, ConfigDict

from nova_guard_api.db.models import ListingStatus


class ListingCreate(BaseModel):
    artifact_id: int | None = None
    gear_snapshot: list | dict | None = None
    seller_character_id: int
    price_credits: int
    outpost_faction_id: int


class ListingPatch(BaseModel):
    price_credits: int | None = None
    status: ListingStatus | None = None


class ListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    artifact_id: int | None
    gear_snapshot: list | dict | None
    seller_character_id: int
    price_credits: int
    outpost_faction_id: int
    expires_at: datetime
    status: str
    etag_version: int


class ListingBulkCreate(BaseModel):
    listings: list[ListingCreate]
