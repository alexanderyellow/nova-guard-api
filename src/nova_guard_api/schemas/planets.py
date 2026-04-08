from pydantic import BaseModel, ConfigDict


class PlanetCreate(BaseModel):
    name: str
    biome: str
    threat_level: int
    ruling_faction_id: int | None = None
    population: int | None = None
    known_resources: list | dict | None = None
    docking_fee: float = 0.0
    quarantined: bool = False
    war_zone: bool = False


class PlanetUpdate(BaseModel):
    name: str | None = None
    biome: str | None = None
    threat_level: int | None = None
    ruling_faction_id: int | None = None
    population: int | None = None
    known_resources: list | dict | None = None
    docking_fee: float | None = None
    quarantined: bool | None = None
    war_zone: bool | None = None


class PlanetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    biome: str
    threat_level: int
    ruling_faction_id: int | None
    population: int | None
    known_resources: list | dict | None
    docking_fee: float
    quarantined: bool
    war_zone: bool
