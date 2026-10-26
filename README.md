# Fleece Detector

**Are you getting fleeced?** Fleece Detector grades fantasy football trades by what they actually do to
*your* team. Instead of just adding up player values, it works out your best starting lineup before and
after the trade, grades the change from A+ to F, and explains the result in plain English.

<!-- Add a screenshot: save one as docs/screenshots/trade-analyzer.png, then uncomment the line below.
![Fleece Detector trade screen](docs/screenshots/trade-analyzer.png)
-->

## My story

I made this because ESPN Fantasy wasn't grading my trades. I was trying to show my friend that the trade I proposed to him was fair so I built this just to find out that my program said I was fleecing him. The hardest part was aligning the players to their projected data because of the names listed on sleeper and espn. My friend ended up not accepting my trade, but I ended up with a nice project to add to my resume. It's lowk tuff tho and im going to continue to use it to try and justify my trades to my leaguemates who are boring and won't make a single trade. And yes I drafted Achane so im desperate.

## Features

- **Trade grades that know your roster.** Picks your optimal lineup before and after the trade, so a third
  good running back who would never start doesn't count as an upgrade.
- **Fair vs. good, kept separate.** A fairness score compares value exchanged; the grade measures your
  lineup change. A trade can be perfectly fair and still be bad for you.
- **Real NFL data.** Rest-of-season projections built from Sleeper's public projections and the nflverse
  schedule, scored with your league's rules (PPR, half, standard or custom).
- **ESPN league import.** Paste a public ESPN league link and your rosters, scoring and real free agents
  fill in automatically. The app never asks for an ESPN password.
- **Moves tab.** Sell-high candidates, safe drops, waiver targets, buy targets, and what's trending on
  Sleeper, each with how much it changes your lineup.
- **Plain-English explanations** generated only from the calculated numbers, never made up.

## Tech stack

| | |
|---|---|
| Backend | Python, FastAPI, Pydantic, SciPy (Hungarian algorithm for optimal lineups), pytest |
| Frontend | React, TypeScript, Vite, Tailwind CSS, Recharts |
| Data | Sleeper public API, nflverse schedule, ESPN public league data |

## How it works

1. **Value every player.** Projected rest-of-season points above a replacement-level player at the same
   position, with the replacement level derived from your league's size and lineup.
2. **Solve the best lineup.** Filling lineup slots, including FLEX, is an assignment problem, solved exactly
   with the Hungarian algorithm (a simple "best player first" approach can get it wrong).
3. **Grade the change.** The percentage change in your projected starting lineup maps to a documented
   A+ to F scale.

The full write-up, including the grade tables, the data pipeline, the API and the security review, is in
[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).

## Run it locally

Requires Python 3.11+ and Node.js 20+.

```powershell
# Terminal 1: backend API (http://localhost:8000)
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload

# Terminal 2: frontend (http://localhost:5173)
cd frontend
npm install
npm run dev
```

Refresh the player data weekly during the season with `python scripts\update_data.py` (in `backend`).

## Tests

```powershell
cd backend
pytest -q
```

114 tests cover trade evaluation, lineup optimization, scoring, the data pipeline, ESPN import failures,
API errors and the security limits.

## Security

No accounts, passwords or API keys exist in the app. All input is validated and size-capped, the API is
rate-limited, and both the API and the site send strict security headers. Dependencies were audited with
`pip-audit` and `npm audit`. Details are in [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md#security).

## License

[MIT](LICENSE). Player projections come from Sleeper's public API and schedules from nflverse. This project
is not affiliated with Sleeper, ESPN or the NFL.
