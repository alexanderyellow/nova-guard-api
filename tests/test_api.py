from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def test_health_no_auth(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_openapi_available(client: TestClient):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "webhooks" in r.json()


def test_rate_limit_headers(client: TestClient):
    ids = client.seed_ids
    h = auth_headers(ids["character_admin"])
    r = client.get("/species", headers=h)
    assert r.status_code == 200
    assert "X-RateLimit-Limit" in r.headers


def test_species_post_forbidden_for_operative(client: TestClient):
    ids = client.seed_ids
    h = auth_headers(ids["character_pilot_op"])
    r = client.post(
        "/species",
        json={"name": "NewSpecies", "home_planet_id": None},
        headers=h,
    )
    assert r.status_code == 403


def test_validation_problem_json(client: TestClient):
    ids = client.seed_ids
    h = auth_headers(ids["character_admin"])
    r = client.post("/species", json={}, headers=h)
    assert r.status_code == 422
    assert r.headers.get("content-type", "").startswith("application/problem+json")


def test_squad_capacity_enforced(client: TestClient):
    ids = client.seed_ids
    cap = auth_headers(ids["character_captain"])
    # shuttle max 4; captain + pilot = 2; add 3 more operatives via admin
    admin = auth_headers(ids["character_admin"])
    new_chars = []
    sid = ids["species_terran"]
    for i in range(3):
        cr = client.post(
            "/characters",
            json={
                "name": f"Filler{i}",
                "species_id": sid,
                "combat_class": "Brawler",
                "reputation": 50,
                "bounty_credits": 0,
                "role": "operative",
                "gear": {},
            },
            headers=admin,
        )
        assert cr.status_code == 201
        new_chars.append(cr.json()["id"])
    for cid in new_chars[:2]:
        r = client.post(
            f"/squads/{ids['squad_with_pilot']}/members",
            json={"character_id": cid},
            headers=cap,
        )
        assert r.status_code == 204
    r = client.post(
        f"/squads/{ids['squad_with_pilot']}/members",
        json={"character_id": new_chars[2]},
        headers=cap,
    )
    assert r.status_code == 409


def test_mission_accept_only_squad_captain(client: TestClient):
    ids = client.seed_ids
    pilot_h = auth_headers(ids["character_pilot_op"])
    r = client.post(
        f"/missions/{ids['mission_high_danger']}/accept",
        json={"squad_id": ids["squad_with_pilot"]},
        headers=pilot_h,
    )
    assert r.status_code == 403


def test_quarantine_requires_reputation_above_75(client: TestClient):
    ids = client.seed_ids
    cap = auth_headers(ids["character_captain"])
    r = client.post(
        f"/missions/{ids['mission_quarantine']}/accept",
        json={"squad_id": ids["squad_with_pilot"]},
        headers=cap,
    )
    assert r.status_code == 422


def test_high_danger_requires_pilot(client: TestClient):
    ids = client.seed_ids
    dealer = auth_headers(ids["character_dealer"])
    r = client.post(
        f"/missions/{ids['mission_high_danger']}/accept",
        json={"squad_id": ids["squad_no_pilot"]},
        headers=dealer,
    )
    assert r.status_code == 422


def test_nova_guard_mission_rejects_high_bounty_crew(client: TestClient):
    ids = client.seed_ids
    cap = auth_headers(ids["character_captain"])
    client.post(
        f"/squads/{ids['squad_with_pilot']}/members",
        json={"character_id": ids["character_operative_bounty"]},
        headers=cap,
    )
    # mission 1 is NG issued on non-quarantine planet, lower danger
    r = client.post(
        f"/missions/{ids['mission_routine']}/accept",
        json={"squad_id": ids["squad_with_pilot"]},
        headers=cap,
    )
    assert r.status_code == 422


def test_contraband_listing_allied_outpost(client: TestClient):
    ids = client.seed_ids
    dealer = auth_headers(ids["character_dealer"])
    r = client.post(
        "/market/listings",
        json={
            "artifact_id": ids["artifact_contraband"],
            "seller_character_id": ids["character_dealer"],
            "price_credits": 500,
            "outpost_faction_id": ids["faction_allied"],
        },
        headers=dealer,
    )
    assert r.status_code == 422


def test_infinity_transfer_dealer_accepted(client: TestClient):
    ids = client.seed_ids
    dealer = auth_headers(ids["character_dealer"])
    r = client.patch(
        f"/artifacts/{ids['artifact_infinity']}/transfer",
        json={"holder_character_id": ids["character_dealer"], "holder_faction_id": None},
        headers=dealer,
    )
    assert r.status_code == 202
    assert r.json().get("job_id") is not None


def test_expired_listing_410(client: TestClient):
    ids = client.seed_ids
    h = auth_headers(ids["character_admin"])
    r = client.get(f"/market/listings/{ids['listing_expired']}", headers=h)
    assert r.status_code == 410


def test_idempotency_key_replays(client: TestClient):
    ids = client.seed_ids
    admin = auth_headers(ids["character_admin"])
    headers = {**admin, "Idempotency-Key": "idem-species-1"}
    body = {"name": "IdemSpecies", "home_planet_id": None}
    r1 = client.post("/species", json=body, headers=headers)
    assert r1.status_code == 201
    r2 = client.post("/species", json=body, headers=headers)
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]
