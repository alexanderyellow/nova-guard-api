from pydantic import BaseModel, ConfigDict


class SpeciesCreate(BaseModel):
    name: str
    home_planet_id: int | None = None
    traits: list | dict | None = None
    known_abilities: list | dict | None = None
    diplomatic_standing: str | None = None


class SpeciesUpdate(BaseModel):
    name: str | None = None
    home_planet_id: int | None = None
    traits: list | dict | None = None
    known_abilities: list | dict | None = None
    diplomatic_standing: str | None = None


class SpeciesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    home_planet_id: int | None
    traits: list | dict | None
    known_abilities: list | dict | None
    diplomatic_standing: str | None
