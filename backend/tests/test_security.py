"""HTTP protections: rate limits, body size cap, input size limits, headers, CORS."""

import pytest
from fastapi.testclient import TestClient

from app.api.security import RateLimitMiddleware, RateRule
from app.main import create_app
from app.services.trending import TrendingService


def make_client(repo, rules=None):
    kwargs = {"rate_rules": rules} if rules else {}
    return TestClient(create_app(repository=repo, trending=TrendingService(fetcher=lambda k: []), **kwargs))


# ---------- rate limiting ----------

def test_rate_limit_returns_429_with_retry_after(repo):
    with make_client(repo, rules=(RateRule("", 3, 60),)) as c:
        codes = [c.get("/health").status_code for _ in range(4)]
        assert codes == [200, 200, 200, 429]
        res = c.get("/health")
        assert res.json()["error"]["code"] == "rate_limited"
        assert int(res.headers["retry-after"]) >= 1


def test_specific_rules_are_separate_from_the_general_one(repo):
    rules = (RateRule("/players", 1, 60), RateRule("", 100, 60))
    with make_client(repo, rules=rules) as c:
        assert c.get("/players").status_code == 200
        assert c.get("/players").status_code == 429
        assert c.get("/health").status_code == 200  # other paths unaffected


def test_window_slides():
    now = [0.0]
    limiter = RateLimitMiddleware(app=None, rules=(RateRule("", 2, 10),), clock=lambda: now[0])
    assert limiter._check("1.2.3.4", "/x") is None
    assert limiter._check("1.2.3.4", "/x") is None
    assert limiter._check("1.2.3.4", "/x") == pytest.approx(10)  # wait the full window
    assert limiter._check("5.6.7.8", "/x") is None  # limits are per client
    now[0] = 10.0
    assert limiter._check("1.2.3.4", "/x") is None  # first hits expired


def test_cors_preflight_is_not_rate_limited(repo):
    with make_client(repo, rules=(RateRule("", 1, 60),)) as c:
        headers = {"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"}
        assert all(c.options("/moves", headers=headers).status_code == 200 for _ in range(3))


# ---------- request size ----------

def test_oversized_body_rejected_with_413(client):
    huge = {"team_a_gives": ["RB1"], "team_a_receives": ["WR1"], "padding": "x" * 70_000}
    res = client.post("/trades/evaluate", json=huge)
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "body_too_large"


def test_oversized_body_without_content_length_rejected(client):
    def chunks():  # streamed body: no Content-Length header, so the size is counted as it arrives
        for _ in range(10):
            yield b"x" * 10_000

    res = client.post("/trades/evaluate", content=chunks(), headers={"Content-Type": "application/json"})
    assert res.status_code == 413


@pytest.mark.parametrize(
    "payload",
    [
        {"team_a_gives": ["RB1"], "team_a_receives": ["WR1"], "team_a_roster": ["RB1"] * 41},  # too many ids
        {"team_a_gives": ["x" * 41], "team_a_receives": ["WR1"]},  # id too long
    ],
)
def test_trade_input_limits(client, payload):
    assert client.post("/trades/evaluate", json=payload).status_code == 422


def test_moves_input_limits(client):
    team = {"team_name": "T", "player_ids": ["RB1"]}
    assert client.post("/moves", json={"league_rosters": [team] * 21}).status_code == 422
    assert client.post("/moves", json={"league_rosters": [{**team, "team_name": "x" * 101}]}).status_code == 422


# ---------- headers, CORS, errors ----------

def test_security_headers_on_api_responses(client):
    h = client.get("/health").headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in h["content-security-policy"]


def test_docs_page_still_works_without_strict_csp(client):
    res = client.get("/docs")
    assert res.status_code == 200
    assert "content-security-policy" not in res.headers
    assert res.headers["x-content-type-options"] == "nosniff"


def test_cors_rejects_unknown_origins(client):
    res = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in res.headers


def test_error_responses_include_cors_and_security_headers(repo):
    with make_client(repo, rules=(RateRule("", 1, 60),)) as c:
        c.get("/health", headers={"Origin": "http://localhost:5173"})
        res = c.get("/health", headers={"Origin": "http://localhost:5173"})
    assert res.status_code == 429
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert res.headers["x-content-type-options"] == "nosniff"


def test_unexpected_errors_do_not_leak_tracebacks(repo):
    app = create_app(repository=repo, trending=TrendingService(fetcher=lambda k: []))

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail")

    with TestClient(app, raise_server_exceptions=False) as c:
        res = c.get("/boom")
    assert res.status_code == 500
    assert "secret internal detail" not in res.text
    assert "Traceback" not in res.text
