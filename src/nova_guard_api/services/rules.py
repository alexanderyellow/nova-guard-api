from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from nova_guard_api.db.models import (
    SHIP_MAX_CREW,
    Alignment,
    Artifact,
    Character,
    CombatClass,
    Faction,
    LegalStatus,
    Mission,
    MissionStatus,
    Planet,
    ShipClass,
    Squad,
)

NOVA_GUARD_BOUNTY_THRESHOLD = 10_000
QUARANTINE_REPUTATION_THRESHOLD = 75.0


def squad_distinct_crew_ids(squad: Squad, db: Session) -> set[int]:
    ids = {squad.captain_character_id}
    for m in squad.members:
        ids.add(m.character_id)
    return ids


def squad_current_size(squad: Squad, db: Session) -> int:
    return len(squad_distinct_crew_ids(squad, db))


def squad_max_crew(ship_class: ShipClass) -> int:
    return SHIP_MAX_CREW[ship_class]


def assert_squad_has_capacity(squad: Squad, db: Session) -> None:
    from fastapi import HTTPException, status

    if squad_current_size(squad, db) >= squad_max_crew(squad.ship_class):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Squad has reached maximum crew for ship class",
        )


def average_squad_reputation(squad: Squad, db: Session) -> float:
    ids = squad_distinct_crew_ids(squad, db)
    if not ids:
        return 0.0
    chars = db.scalars(select(Character).where(Character.id.in_(ids))).all()
    if not chars:
        return 0.0
    return sum(c.reputation for c in chars) / len(chars)


def squad_has_pilot(squad: Squad, db: Session) -> bool:
    ids = squad_distinct_crew_ids(squad, db)
    pilots = db.scalars(
        select(Character).where(Character.id.in_(ids), Character.combat_class == CombatClass.pilot)
    ).all()
    return len(pilots) > 0


def assert_mission_accept_allowed(
    db: Session,
    mission: Mission,
    squad: Squad,
    captain: Character,
) -> None:
    from fastapi import HTTPException, status

    if squad.captain_character_id != captain.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only the squad captain can accept")

    planet = db.get(Planet, mission.target_planet_id)
    if planet is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Target planet not found")

    if planet.quarantined and average_squad_reputation(squad, db) <= QUARANTINE_REPUTATION_THRESHOLD:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Quarantined planet requires squad average reputation above 75",
        )

    if mission.danger_rating > 7 and not squad_has_pilot(squad, db):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missions with danger above 7 require at least one Pilot-class operative in the squad",
        )

    issuer = db.get(Faction, mission.issuer_faction_id)
    if issuer and issuer.is_nova_guard:
        for cid in squad_distinct_crew_ids(squad, db):
            ch = db.get(Character, cid)
            if ch and ch.bounty_credits > NOVA_GUARD_BOUNTY_THRESHOLD:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Characters with bounty over 10,000 cannot join Nova Guard-issued missions",
                )

    if mission.status != MissionStatus.available:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Mission is not available for acceptance",
        )


def assert_listing_contraband_rules(
    db: Session,
    artifact: Artifact | None,
    outpost_faction: Faction,
) -> None:
    from fastapi import HTTPException, status

    if artifact is None or artifact.legal_status != LegalStatus.contraband:
        return
    if outpost_faction.alignment == Alignment.allied:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Contraband artifacts cannot be listed at allied-faction outposts",
        )


def load_squad_with_members(db: Session, squad_id: int) -> Squad | None:
    return db.scalars(select(Squad).where(Squad.id == squad_id).options(selectinload(Squad.members))).first()


def weak_etag_for_version(version: int) -> str:
    return f'W/"v{version}"'


def weak_etag_squad(squad_id: int) -> str:
    return f'W/"squad-{squad_id}"'


def parse_if_match(header: str | None) -> str | None:
    if not header:
        return None
    h = header.strip()
    if h.startswith("W/"):
        h = h[2:].strip()
    if h.startswith('"') and h.endswith('"'):
        return h[1:-1]
    return h
