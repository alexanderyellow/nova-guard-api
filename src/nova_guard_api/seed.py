"""Seed database with demo factions, planets, characters, squads, missions, artifacts."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from nova_guard_api.db.models import (
    Alignment,
    Artifact,
    ArtifactRarity,
    Character,
    CharacterRole,
    CombatClass,
    Faction,
    FactionPlanet,
    LegalStatus,
    ListingStatus,
    MarketListing,
    Mission,
    MissionStatus,
    MissionType,
    Planet,
    ShipClass,
    Species,
    Squad,
    SquadMember,
)


def seed_database(db: Session) -> dict[str, int]:
    """Insert demo rows. Returns stable ids map for documentation."""
    ng = Faction(name="Nova Guard", alignment=Alignment.neutral, is_nova_guard=True)
    rav = Faction(name="Ravager Clans", alignment=Alignment.hostile, is_nova_guard=False)
    allied = Faction(name="Sovereign Collective", alignment=Alignment.allied, is_nova_guard=False)
    db.add_all([ng, rav, allied])
    db.flush()

    p1 = Planet(
        name="Xythos Prime",
        biome="crystal_badlands",
        threat_level=3,
        ruling_faction_id=ng.id,
        population=1_000_000,
        docking_fee=100.0,
        quarantined=False,
    )
    p2 = Planet(
        name="Korval Station",
        biome="orbital",
        threat_level=8,
        ruling_faction_id=rav.id,
        population=50_000,
        docking_fee=500.0,
        quarantined=True,
    )
    p3 = Planet(
        name="Floranic Reach",
        biome="jungle",
        threat_level=2,
        ruling_faction_id=allied.id,
        population=200_000,
        docking_fee=50.0,
        quarantined=False,
    )
    db.add_all([p1, p2, p3])
    db.flush()
    db.add(FactionPlanet(faction_id=rav.id, planet_id=p2.id))

    sp = Species(
        name="Terran",
        home_planet_id=p1.id,
        traits=["adaptable"],
        known_abilities=["survival"],
        diplomatic_standing="neutral",
    )
    db.add(sp)
    db.flush()

    admin = Character(
        name="Admin Command",
        species_id=sp.id,
        combat_class=CombatClass.tactician,
        reputation=99.0,
        bounty_credits=0,
        role=CharacterRole.admin,
        gear={"sidearm": "standard"},
    )
    captain = Character(
        name="Captain Vega",
        species_id=sp.id,
        combat_class=CombatClass.pilot,
        reputation=80.0,
        bounty_credits=0,
        role=CharacterRole.captain,
        gear={},
    )
    pilot_op = Character(
        name="Pilot Kira",
        species_id=sp.id,
        combat_class=CombatClass.pilot,
        reputation=70.0,
        bounty_credits=0,
        role=CharacterRole.operative,
        gear={},
    )
    operative = Character(
        name="Rook",
        species_id=sp.id,
        combat_class=CombatClass.brawler,
        reputation=40.0,
        bounty_credits=15_000,
        role=CharacterRole.operative,
        gear={},
    )
    dealer = Character(
        name="Dealer Mox",
        species_id=sp.id,
        combat_class=CombatClass.tech_specialist,
        reputation=60.0,
        bounty_credits=0,
        role=CharacterRole.dealer,
        gear={},
    )
    db.add_all([admin, captain, pilot_op, operative, dealer])
    db.flush()

    squad = Squad(
        captain_character_id=captain.id,
        ship_name="Stellar Drift",
        ship_class=ShipClass.shuttle,
        reputation=72.0,
    )
    db.add(squad)
    db.flush()
    db.add(SquadMember(squad_id=squad.id, character_id=pilot_op.id))

    squad_no_pilot = Squad(
        captain_character_id=dealer.id,
        ship_name="Iron Haul",
        ship_class=ShipClass.freighter,
        reputation=50.0,
    )
    db.add(squad_no_pilot)
    db.flush()

    m1 = Mission(
        mission_type=MissionType.bounty,
        status=MissionStatus.available,
        reward_credits=5000,
        danger_rating=5,
        issuer_faction_id=ng.id,
        target_planet_id=p1.id,
        title="Routine patrol",
    )
    m2 = Mission(
        mission_type=MissionType.survey,
        status=MissionStatus.available,
        reward_credits=9000,
        danger_rating=8,
        issuer_faction_id=ng.id,
        target_planet_id=p1.id,
        title="High danger survey",
    )
    m3 = Mission(
        mission_type=MissionType.artifact,
        status=MissionStatus.available,
        reward_credits=12_000,
        danger_rating=4,
        issuer_faction_id=ng.id,
        target_planet_id=p2.id,
        title="Quarantined pickup",
    )
    db.add_all([m1, m2, m3])
    db.flush()

    art = Artifact(
        name="Shard of Null",
        origin_planet_id=p1.id,
        rarity=ArtifactRarity.common,
        power_description="Faint hum",
        legal_status=LegalStatus.legal,
        holder_character_id=captain.id,
    )
    contraband = Artifact(
        name="Void Silk",
        origin_planet_id=p2.id,
        rarity=ArtifactRarity.rare,
        power_description="Shadow weave",
        legal_status=LegalStatus.contraband,
        holder_character_id=dealer.id,
    )
    infinity = Artifact(
        name="Omega Lattice",
        origin_planet_id=p3.id,
        rarity=ArtifactRarity.infinity,
        power_description="Infinite recursion",
        legal_status=LegalStatus.restricted,
        holder_faction_id=ng.id,
    )
    db.add_all([art, contraband, infinity])
    db.flush()

    exp = datetime.now(UTC) - timedelta(hours=1)
    expired = MarketListing(
        artifact_id=art.id,
        seller_character_id=captain.id,
        price_credits=100,
        outpost_faction_id=allied.id,
        expires_at=exp,
        status=ListingStatus.active,
        etag_version=1,
    )
    db.add(expired)
    db.commit()

    return {
        "faction_nova_guard": ng.id,
        "faction_allied": allied.id,
        "planet_quarantine": p2.id,
        "character_admin": admin.id,
        "character_captain": captain.id,
        "character_pilot_op": pilot_op.id,
        "character_operative_bounty": operative.id,
        "character_dealer": dealer.id,
        "squad_with_pilot": squad.id,
        "squad_no_pilot": squad_no_pilot.id,
        "mission_routine": m1.id,
        "mission_high_danger": m2.id,
        "mission_quarantine": m3.id,
        "artifact_contraband": contraband.id,
        "artifact_infinity": infinity.id,
        "listing_expired": expired.id,
        "species_terran": sp.id,
    }
