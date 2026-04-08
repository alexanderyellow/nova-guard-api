"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "factions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("alignment", sa.String(length=32), nullable=False),
        sa.Column("is_nova_guard", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "planets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("biome", sa.String(length=64), nullable=False),
        sa.Column("threat_level", sa.Integer(), nullable=False),
        sa.Column("ruling_faction_id", sa.Integer(), nullable=True),
        sa.Column("population", sa.Integer(), nullable=True),
        sa.Column("known_resources", sa.JSON(), nullable=True),
        sa.Column("docking_fee", sa.Float(), nullable=False),
        sa.Column("quarantined", sa.Boolean(), nullable=False),
        sa.Column("war_zone", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["ruling_faction_id"], ["factions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "species",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("home_planet_id", sa.Integer(), nullable=True),
        sa.Column("traits", sa.JSON(), nullable=True),
        sa.Column("known_abilities", sa.JSON(), nullable=True),
        sa.Column("diplomatic_standing", sa.String(length=256), nullable=True),
        sa.ForeignKeyConstraint(["home_planet_id"], ["planets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "characters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("species_id", sa.Integer(), nullable=False),
        sa.Column("combat_class", sa.String(length=32), nullable=False),
        sa.Column("reputation", sa.Float(), nullable=False),
        sa.Column("bounty_credits", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("gear", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["species_id"], ["species.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "faction_planets",
        sa.Column("faction_id", sa.Integer(), nullable=False),
        sa.Column("planet_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["faction_id"], ["factions.id"]),
        sa.ForeignKeyConstraint(["planet_id"], ["planets.id"]),
        sa.PrimaryKeyConstraint("faction_id", "planet_id"),
    )
    op.create_table(
        "squads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("captain_character_id", sa.Integer(), nullable=False),
        sa.Column("ship_name", sa.String(length=128), nullable=False),
        sa.Column("ship_class", sa.String(length=32), nullable=False),
        sa.Column("reputation", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["captain_character_id"], ["characters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "squad_members",
        sa.Column("squad_id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"]),
        sa.ForeignKeyConstraint(["squad_id"], ["squads.id"]),
        sa.PrimaryKeyConstraint("squad_id", "character_id"),
    )
    op.create_table(
        "missions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mission_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reward_credits", sa.Integer(), nullable=False),
        sa.Column("danger_rating", sa.Integer(), nullable=False),
        sa.Column("issuer_faction_id", sa.Integer(), nullable=False),
        sa.Column("target_planet_id", sa.Integer(), nullable=False),
        sa.Column("squad_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.ForeignKeyConstraint(["issuer_faction_id"], ["factions.id"]),
        sa.ForeignKeyConstraint(["squad_id"], ["squads.id"]),
        sa.ForeignKeyConstraint(["target_planet_id"], ["planets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("origin_planet_id", sa.Integer(), nullable=False),
        sa.Column("rarity", sa.String(length=32), nullable=False),
        sa.Column("power_description", sa.Text(), nullable=False),
        sa.Column("legal_status", sa.String(length=32), nullable=False),
        sa.Column("holder_character_id", sa.Integer(), nullable=True),
        sa.Column("holder_faction_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["holder_character_id"], ["characters.id"]),
        sa.ForeignKeyConstraint(["holder_faction_id"], ["factions.id"]),
        sa.ForeignKeyConstraint(["origin_planet_id"], ["planets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "market_listings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("artifact_id", sa.Integer(), nullable=True),
        sa.Column("gear_snapshot", sa.JSON(), nullable=True),
        sa.Column("seller_character_id", sa.Integer(), nullable=False),
        sa.Column("price_credits", sa.Integer(), nullable=False),
        sa.Column("outpost_faction_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("etag_version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"]),
        sa.ForeignKeyConstraint(["outpost_faction_id"], ["factions.id"]),
        sa.ForeignKeyConstraint(["seller_character_id"], ["characters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=256), nullable=False),
        sa.Column("route", sa.String(length=512), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", "route", name="uq_idempotency_key_route"),
    )
    op.create_table(
        "infinity_transfer_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("artifact_id", sa.Integer(), nullable=False),
        sa.Column("target_character_id", sa.Integer(), nullable=True),
        sa.Column("target_faction_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"]),
        sa.ForeignKeyConstraint(["target_character_id"], ["characters.id"]),
        sa.ForeignKeyConstraint(["target_faction_id"], ["factions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("infinity_transfer_jobs")
    op.drop_table("idempotency_keys")
    op.drop_table("market_listings")
    op.drop_table("artifacts")
    op.drop_table("missions")
    op.drop_table("squad_members")
    op.drop_table("squads")
    op.drop_table("faction_planets")
    op.drop_table("characters")
    op.drop_table("species")
    op.drop_table("planets")
    op.drop_table("factions")
