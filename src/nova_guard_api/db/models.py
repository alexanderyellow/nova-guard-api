import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nova_guard_api.db.base import Base

if TYPE_CHECKING:
    pass


class Alignment(str, enum.Enum):
    hostile = "hostile"
    neutral = "neutral"
    allied = "allied"


class CombatClass(str, enum.Enum):
    brawler = "Brawler"
    tactician = "Tactician"
    tech_specialist = "Tech-Specialist"
    mystic = "Mystic"
    pilot = "Pilot"


class CharacterRole(str, enum.Enum):
    captain = "captain"
    operative = "operative"
    dealer = "dealer"
    admin = "admin"


class MissionStatus(str, enum.Enum):
    available = "available"
    accepted = "accepted"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    abandoned = "abandoned"


class MissionType(str, enum.Enum):
    bounty = "bounty_hunt"
    artifact = "artifact_retrieval"
    escort = "escort"
    survey = "planetary_survey"


class ArtifactRarity(str, enum.Enum):
    common = "common"
    uncommon = "uncommon"
    rare = "rare"
    legendary = "legendary"
    infinity = "infinity-class"


class LegalStatus(str, enum.Enum):
    legal = "legal"
    contraband = "contraband"
    restricted = "restricted"


class ListingStatus(str, enum.Enum):
    active = "active"
    sold = "sold"
    cancelled = "cancelled"


class ShipClass(str, enum.Enum):
    shuttle = "shuttle"
    freighter = "freighter"
    cruiser = "cruiser"
    dreadnought = "dreadnought"


SHIP_MAX_CREW: dict[ShipClass, int] = {
    ShipClass.shuttle: 4,
    ShipClass.freighter: 8,
    ShipClass.cruiser: 12,
    ShipClass.dreadnought: 20,
}


class Species(Base):
    __tablename__ = "species"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    home_planet_id: Mapped[int | None] = mapped_column(ForeignKey("planets.id"), nullable=True)
    traits: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    known_abilities: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    diplomatic_standing: Mapped[str | None] = mapped_column(String(256), nullable=True)

    home_planet: Mapped["Planet | None"] = relationship("Planet", foreign_keys=[home_planet_id])


class Faction(Base):
    __tablename__ = "factions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    alignment: Mapped[Alignment] = mapped_column(Enum(Alignment, native_enum=False), nullable=False)
    is_nova_guard: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    controlled_planets: Mapped[list["FactionPlanet"]] = relationship("FactionPlanet", back_populates="faction")


class Planet(Base):
    __tablename__ = "planets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    biome: Mapped[str] = mapped_column(String(64), nullable=False)
    threat_level: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-10
    ruling_faction_id: Mapped[int | None] = mapped_column(ForeignKey("factions.id"), nullable=True)
    population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    known_resources: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    docking_fee: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    quarantined: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    war_zone: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    ruling_faction: Mapped["Faction | None"] = relationship("Faction", foreign_keys=[ruling_faction_id])


class FactionPlanet(Base):
    __tablename__ = "faction_planets"

    faction_id: Mapped[int] = mapped_column(ForeignKey("factions.id"), primary_key=True)
    planet_id: Mapped[int] = mapped_column(ForeignKey("planets.id"), primary_key=True)

    faction: Mapped["Faction"] = relationship("Faction", back_populates="controlled_planets")
    planet: Mapped["Planet"] = relationship("Planet")


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    species_id: Mapped[int] = mapped_column(ForeignKey("species.id"), nullable=False)
    combat_class: Mapped[CombatClass] = mapped_column(Enum(CombatClass, native_enum=False), nullable=False)
    reputation: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    bounty_credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    role: Mapped[CharacterRole] = mapped_column(Enum(CharacterRole, native_enum=False), nullable=False)
    gear: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)

    species: Mapped["Species"] = relationship("Species")


class Squad(Base):
    __tablename__ = "squads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    captain_character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), nullable=False)
    ship_name: Mapped[str] = mapped_column(String(128), nullable=False)
    ship_class: Mapped[ShipClass] = mapped_column(Enum(ShipClass, native_enum=False), nullable=False)
    reputation: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)

    captain: Mapped["Character"] = relationship("Character", foreign_keys=[captain_character_id])
    members: Mapped[list["SquadMember"]] = relationship(
        "SquadMember", back_populates="squad", cascade="all, delete-orphan"
    )


class SquadMember(Base):
    __tablename__ = "squad_members"

    squad_id: Mapped[int] = mapped_column(ForeignKey("squads.id"), primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), primary_key=True)

    squad: Mapped["Squad"] = relationship("Squad", back_populates="members")
    character: Mapped["Character"] = relationship("Character")


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_type: Mapped[MissionType] = mapped_column(Enum(MissionType, native_enum=False), nullable=False)
    status: Mapped[MissionStatus] = mapped_column(Enum(MissionStatus, native_enum=False), nullable=False)
    reward_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    danger_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    issuer_faction_id: Mapped[int] = mapped_column(ForeignKey("factions.id"), nullable=False)
    target_planet_id: Mapped[int] = mapped_column(ForeignKey("planets.id"), nullable=False)
    squad_id: Mapped[int | None] = mapped_column(ForeignKey("squads.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(256), default="", nullable=False)

    issuer_faction: Mapped["Faction"] = relationship("Faction", foreign_keys=[issuer_faction_id])
    target_planet: Mapped["Planet"] = relationship("Planet", foreign_keys=[target_planet_id])
    squad: Mapped["Squad | None"] = relationship("Squad", foreign_keys=[squad_id])


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    origin_planet_id: Mapped[int] = mapped_column(ForeignKey("planets.id"), nullable=False)
    rarity: Mapped[ArtifactRarity] = mapped_column(Enum(ArtifactRarity, native_enum=False), nullable=False)
    power_description: Mapped[str] = mapped_column(Text, nullable=False)
    legal_status: Mapped[LegalStatus] = mapped_column(Enum(LegalStatus, native_enum=False), nullable=False)
    holder_character_id: Mapped[int | None] = mapped_column(ForeignKey("characters.id"), nullable=True)
    holder_faction_id: Mapped[int | None] = mapped_column(ForeignKey("factions.id"), nullable=True)

    origin_planet: Mapped["Planet"] = relationship("Planet", foreign_keys=[origin_planet_id])


class MarketListing(Base):
    __tablename__ = "market_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artifact_id: Mapped[int | None] = mapped_column(ForeignKey("artifacts.id"), nullable=True)
    gear_snapshot: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    seller_character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), nullable=False)
    price_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    outpost_faction_id: Mapped[int] = mapped_column(ForeignKey("factions.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus, native_enum=False), nullable=False)
    etag_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    artifact: Mapped["Artifact | None"] = relationship("Artifact")
    seller: Mapped["Character"] = relationship("Character", foreign_keys=[seller_character_id])
    outpost_faction: Mapped["Faction"] = relationship("Faction", foreign_keys=[outpost_faction_id])


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(256), nullable=False)
    route: Mapped[str] = mapped_column(String(512), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (UniqueConstraint("key", "route", name="uq_idempotency_key_route"),)


class InfinityTransferJob(Base):
    __tablename__ = "infinity_transfer_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artifact_id: Mapped[int] = mapped_column(ForeignKey("artifacts.id"), nullable=False)
    target_character_id: Mapped[int | None] = mapped_column(ForeignKey("characters.id"), nullable=True)
    target_faction_id: Mapped[int | None] = mapped_column(ForeignKey("factions.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
