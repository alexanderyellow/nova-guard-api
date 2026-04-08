from pydantic import BaseModel, ConfigDict

from nova_guard_api.db.models import CharacterRole, CombatClass


class CharacterCreate(BaseModel):
    name: str
    species_id: int
    combat_class: CombatClass
    reputation: float = 50.0
    bounty_credits: int = 0
    role: CharacterRole
    gear: list | dict | None = None


class CharacterPatch(BaseModel):
    name: str | None = None
    combat_class: CombatClass | None = None
    reputation: float | None = None
    bounty_credits: int | None = None
    gear: list | dict | None = None


class CharacterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    name: str
    species_id: int
    combat_class: str
    reputation: float
    bounty_credits: int
    role: str
    gear: list | dict | None


class BountyUpdate(BaseModel):
    bounty_credits: int
