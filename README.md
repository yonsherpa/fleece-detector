# Fleece Detector — Explainable Fantasy Football Trade Evaluator

Fleece Detector tells a fantasy manager whether a trade **actually improves their team**, not just whether the
players' values add up. It values players against a league-specific replacement level, solves each
team's optimal starting lineup before and after the trade, grades each side on a documented scale, and
explains the result in plain English generated only from the numbers it calculated.

> **Data:** real NFL players with rest-of-season projections built from
> [Sleeper](https://docs.sleeper.com)'s public weekly projections and the [nflverse](https://github.com/nflverse/nfldata)
> schedule. Every API response includes when the data was fetched, and the app warns when it's more than 3 days old.

![Trade Analyzer screenshot](docs/screenshots/trade-analyzer.png)
*Screenshot placeholder: take one of the running app and save it to `docs/screenshots/trade-analyzer.png`.*

---

## Project status

| Phase | Scope | Status |
|---|---|---|
| 1 | Project setup and architecture | ✅ Done |
| 2 | FastAPI backend and trade evaluation engine (value + roster-aware + grades + explanations) | ✅ Done |
| 3 | React + Vite + TypeScript + Tailwind trade builder UI, player rankings | ✅ Done |
| 4 | Connect frontend ↔ backend | ✅ Done (built together with Phase 3) |
| 5 | Real player data pipeline (Sleeper projections + nflverse schedule) | ✅ Done |
| 6 | Roster entry, lineup settings, before/after starting lineups | ✅ Done |
| 6b | Moves tab: sell high, safe to drop, waiver targets, buy targets, live Sleeper trends | ✅ Done |
| 7 | ESPN league import (public leagues only): settings, rosters, real free agents | ✅ Done |
| — | Security audit: dependency upgrades, rate limiting, input caps, security headers, CSP | ✅ Done, 114 tests passing |
| 8 | Deployment (Vercel + Render), screenshots, polish | ⏳ |

---

## Architecture

```
tradeiq/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app factory, CORS, error → HTTP mapping
│   │   ├── config.py                # env-var settings
│   │   ├── api/
│   │   │   ├── routes.py            # thin HTTP layer (no business logic)
│   │   │   └── deps.py              # dependency injection (repository, league query params)
│   │   ├── models/                  # Pydantic schemas = the API contract
│   │   │   ├── league.py            # positions, lineup slots, scoring presets
│   │   │   ├── player.py            # player, projection, dataset metadata, PlayerValue
│   │   │   └── trade.py             # TradeRequest / TradeEvaluation
│   │   ├── services/                # all evaluation logic, framework-independent
│   │   │   ├── scoring.py           # stat line → fantasy points
│   │   │   ├── valuation.py         # Stage 1: replacement level + value over replacement
│   │   │   ├── lineup.py            # optimal lineup (Hungarian algorithm)
│   │   │   ├── roster.py            # Stage 2: before/after lineup, drops, open spots
│   │   │   ├── grading.py           # Stage 3: grade tables + fairness
│   │   │   ├── explanations.py      # template-based explanations
│   │   │   ├── trade_evaluator.py   # orchestration + validation
│   │   │   └── player_repository.py # in-memory store + cached valuations
│   │   ├── data/
│   │   │   ├── projection_provider.py  # ProjectionProvider interface + CSV implementation
│   │   │   ├── ingest/
│   │   │   │   ├── sources.py       # network fetchers (Sleeper API, nflverse schedule)
│   │   │   │   └── build.py         # pure transform: raw data → one row per player (unit-tested)
│   │   │   └── snapshot/            # last good real-data snapshot: players.csv + metadata.json
│   │   └── integrations/espn.py     # ESPN fetch + parse (public leagues only), isolated from core logic
│   ├── scripts/update_data.py       # refresh the snapshot (run weekly)
│   ├── tests/                       # pytest suite
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── types/api.ts             # TypeScript mirror of the backend's Pydantic models
│       ├── services/api.ts          # fetch wrapper; turns backend errors into readable messages
│       ├── hooks/                   # usePlayers (search w/ request cancelling), useRoster (saved rosters),
│       │                            # useLeague (scoring, size, lineup slots), useDebounce
│       ├── components/              # AppShell (top bar + tabs), ui primitives (PlayerAvatar, PlayerIdentity…)
│       │   ├── LeagueSwitcher.tsx   # scoring, league size and lineup slots in one panel
│       │   └── trade/               # PlayerSearch, TradePanel (offer sides), Rosters, TradeResults
│       │                            # (Verdict panel + detail tabs), LineupComparison, charts (Recharts)
│       └── pages/                   # TradeAnalyzer, Rankings, ComingSoon
├── .env.example
└── README.md
```

**Request flow for `POST /trades/evaluate`:**

```
JSON → Pydantic validation (models/trade.py)
     → trade_evaluator._validate        (duplicates, rosters, unknown ids)
     → repository.valuation(league)     (Stage 1, cached per league settings)
     → roster.evaluate_roster_change    (Stage 2, only when rosters are supplied)
     → grading                          (Stage 3)
     → explanations                     (plain English from computed numbers)
     → TradeEvaluation JSON
```

**Key design decisions**

- **Layering.** Routes only translate HTTP. Services hold the logic and never import FastAPI, so they are
  unit-tested directly.
- **Swappable data sources.** Everything depends on the `ProjectionProvider` protocol. A future ML model
  provider plugs in without touching valuation or grading.
- **Dependency injection.** `create_app(repository=...)` lets tests inject a small, hand-calculable league.
- **Fail soft on data.** The app serves a saved snapshot, never live API calls, so an outage at Sleeper or
  GitHub can't take it down. A failed refresh leaves the last good snapshot untouched.

---

## Data pipeline

```
Sleeper /state/nfl ─────────► current season + week
Sleeper /players/nfl ───────► names, positions, teams, injury status, ESPN + GSIS ids
Sleeper /projections/…/{w} ─► projected stat line per player, for each week w left in the season
nflverse games.csv ─────────► which games each team still has to play, bye weeks
                 │
                 ▼  app/data/ingest/build.py (pure function)
     rest-of-season stat line = Σ weekly projections over the team's remaining games
     stored as an average per remaining game  →  snapshot/players.csv + metadata.json
```

- **Why stat lines, not Sleeper's points?** Storing yards, TDs and catches lets the engine score
  players under *your* league's rules (PPR, half, standard, custom). As a check, the engine reproduces
  Sleeper's own published PPR totals to within ~0.05 points per game when given Sleeper's rules
  (`test_our_scoring_reproduces_sleeper_ppr_points`).
- **Weeks a player is projected out** count as 0, so injuries lower rest-of-season value automatically.
- **Consistent ids.** Players are keyed `sleeper-<id>`. Each row also carries `gsis_id` (the key nflverse
  uses) and `espn_id` (needed to match ESPN rosters in Phase 7; Sleeper only has it for ~25% of players,
  so that import will need a name-based fallback).
- **Team code mismatch handled.** Sleeper says `LAR`, nflverse says `LA`; `TEAM_ALIASES` maps them.
  Without it every Rams player would appear to have no games left.
- **Sanity checks before saving:** at least 200 players and every position present, or the old
  snapshot is kept.
- **Scope:** QB/RB/WR/TE with at least 1 projected PPR point for the rest of the season. Position is the
  player's *fantasy* position: two-way players and fullbacks are listed as "DB"/"FB" by Sleeper but are
  fantasy-eligible at WR/RB (Travis Hunter was missing until a real league import exposed this).

Refresh the data (do this weekly during the season):

```powershell
cd tradeiq\backend
.\.venv\Scripts\Activate.ps1
python scripts\update_data.py
```

Sleeper's API is free, read-only and needs no login; their docs ask callers to stay under 1,000
requests per minute, and a refresh makes about 14.

---

## The trade evaluation algorithm

### Stage 1: Baseline value (value over replacement)

1. **Points per game** = projected per-game stat line × league scoring rules
   (PPR / half-PPR / standard / custom, including TE premium).
2. **Rest-of-season (ROS) points** = points per game × games remaining.
3. **Replacement level** per position, derived from the league itself:
   - fill every team's dedicated slots (`num_teams × slots`),
   - then fill FLEX/SUPERFLEX slots league-wide with the best remaining eligible players,
   - the best player at each position who would **not start anywhere** is replacement level.
4. **Value over replacement (VOR)** = `max(0, ROS points − replacement ROS points)`.

**Why this matters:**
- **Positional scarcity.** A QB who scores more raw points than an RB can be worth less, because
  replacement-level QBs score a lot too. The test `test_positional_scarcity_beats_raw_points` checks this.
- **Multi-player normalization.** Players below replacement are worth 0, so adding filler to a trade
  doesn't inflate its value. Two bench players can't "add up" to a star
  (`test_two_for_one_filler_does_not_inflate_value`).

### Stage 2: Roster-aware evaluation

When a team's roster is supplied:

```
Trade Impact = Optimal Lineup Points AFTER − Optimal Lineup Points BEFORE   (rest of season)
```

- **Optimal lineup = maximum-weight bipartite matching** between players and slots, solved exactly with
  the Hungarian algorithm (`scipy.optimize.linear_sum_assignment`). Greedy "fill each slot with the best
  remaining player" fails once FLEX overlaps dedicated slots (`test_flex_is_solved_optimally_where_greedy_fails`).
  Each slot gets at most one player and each player at most one slot. Dummy "empty" rows let a slot
  stay empty when no eligible player exists.
- **Roster limit:** if the team ends up over the maximum (e.g. receiving 2-for-1), it drops the player
  whose removal costs the optimal lineup the least, repeating until the roster fits.
- **Open spots:** if the trade frees roster spots (e.g. sending 2-for-1), each is filled with a
  **waiver-level** player at the position that helps the lineup most (like-for-like on ties). Waiver
  level is the best player beyond the number of players a league typically rosters at that position.
- **Positional breakdown:** starter points and best bench player (depth) per position, before and after.

### Stage 3: Grades and fairness

Each team is graded separately; the headline grade is **Team A's** (the user's).

| Method | When used | Score |
|---|---|---|
| `roster_aware` | that team's roster was supplied | % change in projected optimal starting lineup |
| `value_only` | no roster | `(VOR received − VOR given) / max(received, given) × 100` |

| Grade | roster_aware score ≥ | value_only score ≥ |
|---|---|---|
| A+ | 6.0 | 35 |
| A | 4.5 | 25 |
| A- | 3.0 | 20 |
| B+ | 2.0 | 15 |
| B | 1.25 | 10 |
| B- | 0.5 | 5 |
| C+ | 0.0 | 0 |
| C | −0.5 | −5 |
| C- | −1.25 | −10 |
| D+ | −2.0 | −15 |
| D | −3.0 | −20 |
| D- | −4.5 | −35 |
| F | below | below |

A neutral trade scores **C+/C**. The value-only table is aligned with the fairness labels below:
giving up at most 10% of value ("very fair") stays in the C range, and only a "lopsided" loss
(more than 35%) is an F. The roster-aware thresholds are small percentages because a whole
starting lineup is ~1,500 ROS points: +3% (~45 points) is a meaningful upgrade.

**Fairness is a separate question.** `fairness = 100 × min(VOR_A_receives, VOR_B_receives) / max(...)`
(≥90 very fair, ≥80 fair, ≥65 uneven, else lopsided). A trade can be perfectly fair and still help one
team far more than the other, because their rosters need different things. The test
`test_complementary_needs_fair_trade_can_help_both` shows a 100/100 fair trade that improves both lineups.

**Winner:** if both rosters are supplied, the team with the larger lineup % gain (within 0.5% counts as
even). Otherwise, the side receiving more VOR. The response field `winner_basis` says which was used.

### Explanations

`services/explanations.py` builds sentences only from computed fields (lineup deltas, per-position
starter and depth changes, forced drops, open roster spots, reported injury status). If an LLM is added
later, it should receive only this structured output, so it can rephrase the results but not invent them.

The headline verdict in the UI is a fixed lookup on Team A's grade letter, so it never adds its own judgment:

| Grade | Verdict |
|---|---|
| A | You're doing the fleecing |
| B | Nice pickup |
| C | No fleece here |
| D | Fleece warning |
| F | You're getting fleeced |

### ESPN league import

**What we found when researching ESPN (October 2026).** ESPN has no official public fantasy API. Its own
website reads league data from `lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/segments/0/leagues/{id}`
with `view=mSettings&view=mTeam&view=mRoster`. Public leagues answer without a login; private leagues answer
**401** unless the request carries the owner's `espn_s2`/`SWID` session cookies. Code tables (lineup slot
ids, position ids, scoring stat ids, team ids) follow the open-source
[espn-api](https://github.com/cwendt94/espn-api) project.

**Decisions:**
- Public leagues only. The app never asks for an ESPN password or cookies; a private league gets a clear
  message (make it viewable, or enter the roster by hand on the Trade page).
- Everything ESPN-specific lives in `app/integrations/espn.py` (fetch + parse). Turning a league into our
  settings is `app/services/league_import.py`, and matching players is `app/services/player_matching.py`.
- Only team names are imported, not managers' personal names.
- Only the current season (the season our projections cover) can be imported. League data is cached for
  5 minutes.

**Conversion:**

| ESPN | Fleece Detector |
|---|---|
| Lineup slots 0/2/4/6/23/7/20 | QB/RB/WR/TE/FLEX/Superflex/Bench. RB/WR and WR/TE flex count as FLEX (approximation) |
| K and D/ST slots/players | Left out (not modeled), reported in notes |
| IR slot | Player listed, but left out of the roster used for grading |
| Scoring stat ids (3, 4, 20, 24, 25, 42, 43, 53, 72, 19/26/44) | Points per yard / TD / reception / INT / fumble / 2-pt |
| "Every N yards" ids (5–10, 27–31, 47–49) | Points per yard = points ÷ N (ESPN scores whole increments) |
| TE override on receptions (`pointsOverrides["6"]`) | `te_reception_bonus` |
| Other offensive bonuses | Counted and reported as "not modeled" |

If the converted scoring equals a preset it's labeled PPR / Half PPR / Standard; otherwise it's sent as
custom scoring (the GET endpoints accept `scoring_format=custom&scoring=reception:0.5,...`).

**Player matching** (`player_matching.py`): ESPN id first (Sleeper only has it for ~25% of players), then
normalized name + position ("T.J. Hockenson" = "TJ Hockenson", "Kenneth Walker III" = "Kenneth Walker"),
then a unique normalized name. Ambiguous or unknown players are listed as unmatched, never guessed.

**What the import unlocks:** your roster stays synced with your ESPN team, "their roster" can be any league
team in one click, Moves shows **real free agents** (on nobody's roster) instead of a rank estimate, and buy
targets are limited to players another team owns, labeled with that team. "Trade for" loads the owning team
as the trade partner so both sides are graded by lineup.

### Moves: roster suggestions

`services/moves.py` reuses the optimal-lineup engine to answer "what should I do with my roster?":

- **Lineup cost** of a player = best lineup now − best lineup without them.
- **Lineup gain** of a player = best lineup with them − best lineup now (if the roster is full, the player
  whose loss hurts least is dropped to make room, using the same rule as trades).

| Section | Rule |
|---|---|
| Sell high | value ≥ 5 **and** lineup cost ≤ 25% of value: other teams would pay for them, you barely use them |
| Safe to drop | value ≤ 1 (replacement level) **and** lineup cost ≤ 0.5 |
| Waiver targets | ranked below `num_teams × roster size` overall, so likely unrostered; sorted by lineup gain |
| Buy targets | biggest lineup gains among players worth ≤ ~110% of your best sell-high piece (what you can afford) |
| Trending | live most-added/dropped players across Sleeper (last 24h), with your lineup gain for each |

Trending is fetched live (it's only meaningful when fresh), cached for 30 minutes, and if Sleeper is
unreachable that one section says so while everything else still works. Waiver targets are an estimate
until league import exists: without your league's actual rosters the app can only say "likely unrostered".

A useful honest result: for a deep roster, the most-added players on Sleeper usually add **+0** to your
lineup. The UI says so ("Popular isn't the same as useful to you") instead of hiding it.

### Stage 4: ML readiness

Projections enter only through `ProjectionProvider.load()`. To use a trained model (e.g. gradient
boosting on nflverse weekly data predicting ROS points per game), implement a `ModelProjectionProvider`
that outputs the same `Player` objects. Valuation, lineup optimization, grading and the API stay unchanged.
No ML is faked in the current build.

### Known limitations (be upfront about these in interviews)

- K and D/ST are not modeled yet (lineups are QB/RB/WR/TE/FLEX/SUPERFLEX).
- ROS totals ignore bye-week overlap within a lineup (a player on bye is treated as contributing their
  average). Week-by-week lineup optimization would fix this.
- Injury status is shown as reported; it only affects value via `games_remaining` in the data.
- Grade thresholds are hand-chosen, documented constants, not fitted to outcome data.

---

## API

Interactive docs are auto-generated at **http://localhost:8000/docs** (Swagger) and `/redoc`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness + which dataset is loaded |
| GET | `/meta` | Scoring presets, default lineup, positions (for frontend forms) |
| GET | `/dataset` | Dataset source, season/week, `as_of` timestamp |
| GET | `/players?q=&position=&limit=&scoring_format=&num_teams=&lineup=` | Search, best value first |
| GET | `/players?ids=sleeper-9221,sleeper-9488` | Look up specific players (used for saved rosters); unknown ids are skipped |
| POST | `/moves` | `{roster, league}` → sell high, safe to drop, waiver targets, buy targets, trending adds/drops |
| GET | `/players/{player_id}` | One player's computed value |
| POST | `/trades/evaluate` | Full evaluation |
| GET | `/leagues/{league_id}?season=` | Import a public ESPN league: settings, scoring, every team matched to our players |
| GET | `/leagues/{league_id}/teams` | Just the imported teams and rosters |

`lineup` uses `SLOT:COUNT` pairs, e.g. `QB:1,RB:2,WR:3,TE:1,FLEX:1,SUPERFLEX:0,BENCH:6`; omitted slots keep
the ESPN defaults. Lineup slots change replacement levels, so GET values match what `POST /trades/evaluate`
uses for the same league.

**Rosters in the UI.** "Your roster" is saved in the browser (`localStorage`, ids only; values are re-fetched
for the current league settings). "Their roster" is optional and kept only for the visit. With a roster, the
"gives" picker only offers your players, and the grade switches from value-based to roster-aware.

Example request:

```json
POST /trades/evaluate
{
  "team_a_gives": ["sleeper-9221"],
  "team_a_receives": ["sleeper-9488"],
  "team_a_roster": null,
  "team_b_roster": null,
  "league": {
    "num_teams": 12,
    "scoring_format": "ppr",
    "lineup": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "SUPERFLEX": 0, "BENCH": 7}
  }
}
```

Errors use one shape: `{"error": {"code": "...", "message": "..."}}`.
`404 unknown_player` for bad ids; `422 invalid_trade` for duplicates, a player on both sides, trading a
player who isn't on the roster, or an oversized roster. Malformed JSON gets FastAPI's standard 422.

---

## Setup (Windows, VS Code, PowerShell)

Requirements: **Python 3.11+**, **Node.js 20+** (https://nodejs.org) and **Git** (https://git-scm.com).
On Windows 11: `winget install OpenJS.NodeJS.LTS` and `winget install Git.Git`.

You run two servers, each in its own terminal (VS Code: Terminal → New Terminal, then the split icon).

**Terminal 1: backend API** (http://localhost:8000)

```powershell
cd tradeiq\backend
python -m venv .venv                  # first time only
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements-dev.txt   # first time only (runtime + test tools)
uvicorn app.main:app --reload
```

**Terminal 2: frontend** (http://localhost:5173)

```powershell
cd tradeiq\frontend
npm install                           # first time only
npm run dev
```

Open **http://localhost:5173** for the app, or http://localhost:8000/docs for the interactive API docs.
The frontend reads the API address from `VITE_API_BASE_URL` (default `http://localhost:8000`).
If the header says "API offline", the backend terminal isn't running.

**Frontend design notes**
- **"Sleeper night" theme:** Sleeper-inspired navy neutrals (`ink`), one mint accent (`mint`), and Sleeper's
  position colors (QB pink, RB teal, WR blue, TE orange) for position pills. Vercel-style structure: a top
  bar with a league switcher, tabs instead of a sidebar, flat bordered cards, Inter for text and Geist Mono
  for numbers. All tokens live in `frontend/tailwind.config.js`.
- **Logo and mascot:** the football thief, a football in a knit beanie and robber's mask (`BrandMark.tsx`, same
  art as `public/favicon.svg`), designed to stay readable at 16 px in a browser tab. The mascot
  (`ThiefMascot.tsx`) reuses the same art, running off with a sack of wool on placeholder pages and D/F
  verdicts. Both are original SVGs.
- **Headshots** come from Sleeper's CDN using the Sleeper id in each `player_id`; if a photo is missing the
  avatar falls back to initials.
- **Chart colors** (pink = you send, deeper mint = you receive) were checked with a color-vision-deficiency
  validator. Their colorblind separation is in the "allowed with labels" band, so every bar is also
  labeled with its value and the legend names both sides. RB teal and WR blue are too close to use as
  chart colors, so position colors only appear on pills that also say the position.
- Every number on screen comes from the API. The frontend only adds up or groups values the backend
  returned (e.g. net value per position), and never estimates anything itself.

> If `pip install` fails with `No module named 'pip._internal.utils'` or similar, the project path is
> too long for Windows' 260-character limit. Move the project to a short path (e.g. `C:\dev\tradeiq`)
> or enable long paths in Windows.

Refresh player data before a session if the header shows an old "updated" date:

```powershell
python scripts\update_data.py
```

### Tests

```powershell
cd tradeiq\backend
pytest -q
```

Test coverage includes equal-value, 1-for-1, 2-for-1 and lopsided trades; invalid and duplicate players;
missing projections; PPR/half/standard/custom scoring; FLEX/SUPERFLEX optimization; positional scarcity;
trades that help one team and hurt the other; roster limits; data-source failures and fallback; HTTP
error codes and CORS. ESPN integration failure tests arrive with Phase 7.

---

## Deployment (planned, Phase 8)

- **Backend → Render** (free web service): root directory `backend`, build `pip install -r requirements.txt`,
  start `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*"`
  (never `--reload` in production; `--proxy-headers` makes rate limiting see each visitor's real IP instead
  of Render's proxy), env var `FLEECE_CORS_ORIGINS=https://<your-app>.vercel.app`.
- **Frontend → Vercel**: root `frontend`, env var `VITE_API_BASE_URL=https://<your-api>.onrender.com`.
  Security headers come from `frontend/vercel.json`. Its CSP allows API calls to `https://*.onrender.com`;
  if the API gets a custom domain, add it to `connect-src` there.

---

## Security

Audited October 2026 with tools, not just a checklist. What applies to this app:

| Area | Status |
|---|---|
| Secrets / API keys | None exist: Sleeper and ESPN public data need no keys. `.env` is git-ignored; the only env vars are non-secret (allowed CORS origins, data source path, API URL). Git history scanned for secret patterns: clean. |
| Logins, passwords, admin routes, user access | **Not applicable by design**: no accounts, no admin endpoints, no database of users. Rosters live only in each visitor's own browser (`localStorage`). The app refuses to handle ESPN login cookies. |
| Database | None (data is a read-only CSV snapshot). |
| Input validation | Every request is validated by Pydantic: types, enums, numeric ranges, and size caps on every list and string (`PlayerId` ≤ 40 chars, rosters ≤ 40 ids, ≤ 20 league teams). Request bodies over 64 KB are refused with 413, even when streamed without a Content-Length. |
| Injection | No SQL, shell commands, `eval`, or user-controlled file paths in the backend. The ESPN URL is built only from an integer league id. |
| XSS | React escapes all rendered text; the frontend uses no `dangerouslySetInnerHTML`, `innerHTML` or `eval`. A strict Content Security Policy (`frontend/vercel.json`) blocks scripts from anywhere but the site itself. |
| Rate limiting | Per-IP sliding window (`app/api/security.py`): 10/min for ESPN import, 30/min for Moves (calls Sleeper), 120/min overall. Returns 429 with `Retry-After`. In-memory, so it assumes one server instance. |
| CORS | Only the configured frontend origin(s); `GET`/`POST`; `Content-Type` header only; no credentials. |
| Security headers | API: `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, HSTS, `Permissions-Policy`, and `default-src 'none'` CSP (relaxed only for `/docs`). Frontend: CSP, `nosniff`, `DENY`, referrer policy, HSTS, permissions policy. The CSP was tested locally with `npm run preview`, which serves the built site with the same headers. |
| Debug / error leakage | FastAPI `debug=False`; unexpected errors return a plain 500 with no traceback (tested). No source maps are published. |
| Dependencies | `pip-audit` and `npm audit`: Starlette/FastAPI upgraded (fixed 8 advisories), React Router 6 → 7 and Vite 5 → 6 (fixed open-redirect and dev-server advisories). Shipped frontend code: 0 known vulnerabilities. Test tools moved to `requirements-dev.txt` so they're not installed in production. |

**Accepted risk:** `npm audit` still reports 3 *moderate* advisories in Tailwind CSS 3's selector parser
(slow parsing of crafted CSS). It runs only at build time on our own CSS, never on visitor input; the fix
requires Tailwind 4 (a config rewrite), noted under future improvements.

Re-run the checks anytime:

```powershell
cd backend; .\.venv\Scripts\python.exe -m pip_audit -r requirements-dev.txt
cd frontend; npm audit --omit=dev
```

---

## What to understand for interviews

1. **Why not just sum player values?** Because roster context decides value: a third good RB may never
   start. Fleece Detector measures the change in *optimal starting lineup*.
2. **Why value over replacement?** It makes positions comparable and stops "quantity over quality"
   trades from looking good.
3. **Why the Hungarian algorithm?** Lineup setting with FLEX slots is an assignment problem. Greedy
   can be suboptimal, while the Hungarian algorithm is exact and deterministic. Be ready to walk through
   the greedy counterexample in `tests/test_lineup.py`.
4. **Fair vs. good.** Fairness compares value exchanged; grades measure each team's lineup change.
5. **Testability.** Services are pure Python, the repository is injected, and the fixture league is small
   enough to verify every expected number by hand (see the comments in `tests/conftest.py`).
6. **Data honesty.** Every response says where the data came from and when. Old data triggers a warning,
   missing projections are flagged rather than guessed, and the scoring engine is checked against
   Sleeper's own published points.
7. **Real-world data problems.** Be ready to tell the `LAR` vs `LA` story: two sources disagreed on one
   team code, which would have silently zeroed every Rams player. Cross-source joins need explicit checks.
8. **Reusing one engine for a second feature.** Moves didn't need new math: "lineup cost" and "lineup
   gain" are just the trade engine's optimal-lineup function called with one player removed or added.
   A test caught my own wrong expectation (RB2 also counts as surplus once RB3 and RB4 can move up),
   which is a good story about trusting tested logic over intuition.
9. **Integrating an unofficial API responsibly.** Be ready to explain the ESPN research: no official API,
    public vs. private leagues (401), why the app refuses to collect login cookies, how failures map to
    clear messages (404 → "no such league", 401/403 → "private", network/5xx → "ESPN unavailable"), and why
    all of it is tested offline with a fake HTTP transport.
10. **A frontend race condition.** Typing a name and pressing Enter before search results arrived used to add
   the wrong player, because for one render the *previous* results were still on screen. The fix: results
   remember which query they belong to (`resultsFor` in `usePlayers`), and an early Enter waits for the
   matching results. Checking a `loading` flag alone isn't enough, which is a good example of why async UI
   state needs an explicit "what is this data for" check.

## Future improvements

- Scheduled weekly data refresh (e.g. a GitHub Action running `scripts/update_data.py`)
- Show real season-to-date stats from nflverse weekly player stats next to projections
- Week-by-week lineup simulation using bye weeks and schedule strength
- Trained ROS projection model with backtesting against prior seasons
- Uncertainty: projection ranges and a floor/ceiling view of the trade
- K and D/ST support; dynasty/keeper value; SQLite-backed trade history
- Optional LLM rephrasing grounded only in the structured evaluation
- Upgrade to Tailwind CSS 4 (clears the remaining build-time npm advisory) and React 19
- Shared rate-limit store (e.g. Redis) if the API ever runs on more than one instance
- Run `pytest`, `pip-audit` and `npm audit` automatically on every push (GitHub Actions)

---

## License

[MIT](LICENSE). Player projections come from Sleeper's public API and schedules from nflverse; this project is not affiliated with Sleeper, ESPN or the NFL.
