from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from nova_guard_api.api.deps import is_admin, require_any_auth
from nova_guard_api.api.idempotency_helper import replay_if_idempotent, save_idempotent
from nova_guard_api.core.pagination import hateoas_links, run_paginated
from nova_guard_api.core.security import Actor
from nova_guard_api.db.models import Artifact, CharacterRole, Faction, ListingStatus, MarketListing
from nova_guard_api.db.session import get_db
from nova_guard_api.schemas.market import ListingBulkCreate, ListingCreate, ListingOut, ListingPatch
from nova_guard_api.services.rules import assert_listing_contraband_rules, parse_if_match
from nova_guard_api.services.webhooks import dispatch_webhook_sync

router = APIRouter(prefix="/market", tags=["market"])

LISTING_TTL = timedelta(hours=72)


def can_post_listing(actor: Actor) -> bool:
    return is_admin(actor) or actor.role == CharacterRole.captain or actor.role == CharacterRole.dealer


def weak_etag_listing(listing: MarketListing) -> str:
    return f'W/"listing-{listing.id}-v{listing.etag_version}"'


@router.get("/listings")
def list_listings(
    request: Request,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_any_auth),
    cursor: str | None = None,
    limit: int = 20,
):
    stmt = select(MarketListing).where(MarketListing.status == ListingStatus.active)
    rows, next_c = run_paginated(db, stmt, MarketListing.id, limit=limit, cursor=cursor)
    now = datetime.now(UTC)
    items = []
    for r in rows:
        if r.expires_at.replace(tzinfo=r.expires_at.tzinfo or UTC) <= now:
            continue
        items.append(ListingOut.model_validate(r).model_dump())
    self_href = str(request.url).split("?")[0]
    return {
        "items": items,
        "next_cursor": next_c,
        "_links": hateoas_links(self_href=self_href, next_cursor=next_c),
    }


@router.post("/listings", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
def create_listing(
    request: Request,
    body: ListingCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if not can_post_listing(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cannot create listings")
    replay = replay_if_idempotent(request, db, idempotency_key)
    if replay:
        return replay
    artifact = None
    if body.artifact_id is not None:
        artifact = db.get(Artifact, body.artifact_id)
        if artifact is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    outpost = db.get(Faction, body.outpost_faction_id)
    if outpost is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Outpost faction not found")
    assert_listing_contraband_rules(db, artifact, outpost)
    if not is_admin(actor) and actor.id != body.seller_character_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Listings must be posted for yourself unless admin",
        )
    expires = datetime.now(UTC) + LISTING_TTL
    row = MarketListing(
        artifact_id=body.artifact_id,
        gear_snapshot=body.gear_snapshot,
        seller_character_id=body.seller_character_id,
        price_credits=body.price_credits,
        outpost_faction_id=body.outpost_faction_id,
        expires_at=expires,
        status=ListingStatus.active,
        etag_version=1,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    out = ListingOut.model_validate(row).model_dump()
    save_idempotent(request, db, idempotency_key, 201, out)
    return row


@router.get("/listings/{listing_id}")
def get_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_any_auth),
):
    row = db.get(MarketListing, listing_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Listing not found")
    now = datetime.now(UTC)
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    if exp <= now:
        raise HTTPException(status.HTTP_410_GONE, detail="Listing has expired")
    payload = ListingOut.model_validate(row).model_dump()
    return JSONResponse(content=payload, headers={"ETag": weak_etag_listing(row)})


@router.patch("/listings/{listing_id}", response_model=ListingOut)
def patch_listing(
    listing_id: int,
    body: ListingPatch,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
    if_match: str | None = Header(default=None, alias="If-Match"),
):
    row = db.get(MarketListing, listing_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Listing not found")
    now = datetime.now(UTC)
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    if exp <= now:
        raise HTTPException(status.HTTP_410_GONE, detail="Listing has expired")
    if not is_admin(actor) and actor.id != row.seller_character_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not listing owner")
    if if_match:
        expected = parse_if_match(weak_etag_listing(row))
        got = parse_if_match(if_match)
        if got != expected:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, detail="ETag mismatch")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    row.etag_version = row.etag_version + 1
    db.commit()
    db.refresh(row)
    return row


@router.delete("/listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
):
    row = db.get(MarketListing, listing_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if not is_admin(actor) and actor.id != row.seller_character_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not listing owner")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/listings/{listing_id}/buy", response_model=ListingOut)
def buy_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
):
    row = db.get(MarketListing, listing_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Listing not found")
    now = datetime.now(UTC)
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    if exp <= now:
        raise HTTPException(status.HTTP_410_GONE, detail="Listing has expired")
    if row.status != ListingStatus.active:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Listing not active")
    row.status = ListingStatus.sold
    db.commit()
    db.refresh(row)
    dispatch_webhook_sync(
        "market.listing_sold",
        {"listing_id": listing_id, "buyer_character_id": actor.id, "price": row.price_credits},
    )
    return row


@router.post("/listings/bulk", status_code=status.HTTP_201_CREATED)
def bulk_listings(
    body: ListingBulkCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
):
    if not (is_admin(actor) or actor.role == CharacterRole.dealer):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin or dealer only")
    created = []
    for item in body.listings:
        artifact = None
        if item.artifact_id is not None:
            artifact = db.get(Artifact, item.artifact_id)
            if artifact is None:
                continue
        fac = db.get(Faction, item.outpost_faction_id)
        if fac is None:
            continue
        try:
            assert_listing_contraband_rules(db, artifact, fac)
        except HTTPException:
            continue
        expires = datetime.now(UTC) + LISTING_TTL
        row = MarketListing(
            artifact_id=item.artifact_id,
            gear_snapshot=item.gear_snapshot,
            seller_character_id=item.seller_character_id,
            price_credits=item.price_credits,
            outpost_faction_id=item.outpost_faction_id,
            expires_at=expires,
            status=ListingStatus.active,
            etag_version=1,
        )
        db.add(row)
        db.flush()
        created.append(ListingOut.model_validate(row).model_dump())
    db.commit()
    return {"created": created, "count": len(created)}
