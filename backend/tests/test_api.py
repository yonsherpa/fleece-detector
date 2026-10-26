def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["players_loaded"] > 0
    assert body["dataset"]["source"] == "unit_test_fixture"


def test_players_search_and_filters(client):
    res = client.get("/players", params={"position": "TE", "num_teams": 4, "limit": 3})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 8
    assert [p["player_id"] for p in body["players"]] == ["TE1", "TE2", "TE3"]  # best value first

    res = client.get("/players", params={"q": "rb1"})
    ids = {p["player_id"] for p in res.json()["players"]}
    assert "RB1" in ids and "RB16" in ids and "WR1" not in ids


def test_position_query_filters_by_position(client):
    res = client.get("/players", params={"q": "te", "num_teams": 4})
    assert {p["position"] for p in res.json()["players"]} == {"TE"}


def test_players_by_ids_skips_unknown(client):
    res = client.get("/players", params={"ids": "RB1,GHOST,QB1,RB1", "num_teams": 4})
    assert res.status_code == 200
    assert sorted(p["player_id"] for p in res.json()["players"]) == ["QB1", "RB1"]


def test_lineup_query_changes_replacement_level(client):
    base = client.get("/players/RB1", params={"num_teams": 4}).json()
    no_flex = client.get("/players/RB1", params={"num_teams": 4, "lineup": "FLEX:0"}).json()
    assert base["replacement_ros_points"] == 100  # see tests/conftest.py
    assert no_flex["replacement_ros_points"] == 120  # fewer RBs start league-wide -> higher bar


def test_invalid_lineup_query_is_422(client):
    assert client.get("/players", params={"lineup": "RB:two"}).status_code == 422
    assert client.get("/players", params={"lineup": "KICKER:1"}).status_code == 422
    assert client.get("/players", params={"lineup": "RB:9"}).status_code == 422


def test_get_player_and_unknown_player(client):
    res = client.get("/players/QB1", params={"num_teams": 4})
    assert res.status_code == 200
    assert res.json()["projected_ros_points"] == 240

    res = client.get("/players/NOPE")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "unknown_player"


def test_evaluate_trade_endpoint(client):
    payload = {
        "team_a_gives": ["RB1"],
        "team_a_receives": ["RB9"],
        "league": {"num_teams": 4, "scoring_format": "standard"},
    }
    res = client.post("/trades/evaluate", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["grade"] == "F"
    assert body["winner"] == "team_b"
    assert body["explanation"]["summary"]
    assert {"fairness", "team_a", "team_b", "players_given", "dataset"} <= body.keys()


def test_evaluate_rejects_duplicates_with_422(client):
    res = client.post("/trades/evaluate", json={"team_a_gives": ["RB1", "RB1"], "team_a_receives": ["WR1"]})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_trade"


def test_evaluate_unknown_player_404(client):
    res = client.post("/trades/evaluate", json={"team_a_gives": ["RB1"], "team_a_receives": ["GHOST"]})
    assert res.status_code == 404
    assert res.json()["error"]["player_ids"] == ["GHOST"]


def test_evaluate_schema_validation(client):
    # Empty side and an invalid scoring format are rejected by Pydantic before any logic runs.
    assert client.post("/trades/evaluate", json={"team_a_gives": [], "team_a_receives": ["WR1"]}).status_code == 422
    bad_league = {"team_a_gives": ["RB1"], "team_a_receives": ["WR1"], "league": {"scoring_format": "6pt"}}
    assert client.post("/trades/evaluate", json=bad_league).status_code == 422


def test_cors_allows_vite_dev_server(client):
    res = client.options(
        "/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"
