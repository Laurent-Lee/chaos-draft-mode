# CLAUDE.md — CR Draft Codebase Guide

This file is the authoritative reference for working on the CR Draft codebase. Read it fully before making any changes.

---

## What This App Does

CR Draft is a local two-player ban/pick draft tool for **Clash Royale's C.H.A.O.S. mode**. It runs as a Flask web server on `localhost:5050`. Two players sit at the same machine and take turns banning and picking cards from the 50-card CHAOS pool. At the end, each player gets a deep-link to import their drafted deck directly into Clash Royale on their phone.

It also tracks match history, per-card win/pick/ban rates, and ELO ratings across sessions via CSV files.

---

## Project Structure

```
cr_draft/
├── main.py              # Entry point — Flask app init, Blueprint registration, startup
├── config.py            # All constants and paths — the single source of truth
├── .env                 # CR API token (never commit this)
│
├── backend/
│   ├── cards.py         # CR API fetch + deck link generation
│   ├── draft.py         # Global state dict, draft logic, draft API Blueprint
│   ├── stats.py         # CSV I/O, match history, card/player stats, ELO Blueprint
│   └── elo.py           # ELO calculator (external, must export calculate_elo, OUTPUT_CSV, INPUT_CSV)
│
├── frontend/
│   ├── frontend.py      # Frontend Blueprint — serves /, /player_stats, /elixir.svg, /stats
│   ├── stats.html       # Card stats page (external, served at /stats)
│   └── templates/
│       ├── index.html        # Main draft UI
│       └── player_stats.html # Player leaderboard + per-player detail (Stats + Recent Matches tabs)
│
├── static/
│   ├── elixir.svg       # Elixir icon served at /elixir.svg via frontend Blueprint
│   ├── card_tiers.js    # CARD_TIER, TIER_ORDER, TIER_ICONS — edit to rebalance tiers
│   └── card_types.js    # CARD_TYPE, TYPE_ORDER, TYPE_ICONS — edit to reclassify cards
│
└── data/
    ├── output.csv        # Match history — auto-created on first recorded game
    └── elo.csv           # ELO ratings — written by elo.py after each match
```

---

## Architecture

### Flask Blueprints
The app uses three Blueprints registered in `main.py`:
- `draft_bp` (from `backend/draft.py`) — all `/api/` draft routes
- `stats_bp` (from `backend/stats.py`) — all `/api/` stats routes
- `frontend_bp` (from `frontend/frontend.py`) — page and asset routes

`config.py` and `backend/cards.py` are pure utility modules — they define no routes and are imported by the Blueprints.

### Global State
All live draft state lives in a single dict in `backend/draft.py`:

```python
state = {
    "cards":        [],   # full CHAOS card list fetched from CR API (cached for session)
    "pool":         [],   # cards still available to ban/pick
    "banned":       [],   # list of {"card": {...}, "by": 1 | 2 | "random"}
    "p1_picks":     [],
    "p2_picks":     [],
    "phase":        "setup",  # "setup" | "ban" | "pick" | "done"
    "action_index": 0,        # current position in BAN_SEQUENCE or PICK_SEQUENCE
    "p1_name":      ...,
    "p2_name":      ...,
    "1st_pick":     ...,      # player name who holds slot 1 in PICK_SEQUENCE
    "2nd_pick":     ...,
}
```

This is a module-level global — intentional for simplicity. It is imported directly by `backend/stats.py`. Do not refactor it into a class without updating both files.

### Path Resolution
All file paths are anchored to `_ROOT` in `config.py`:

```python
_ROOT    = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(_ROOT, "data", "output.csv")
```

**Never use bare relative paths** like `"data/output.csv"` — they break depending on where `python main.py` is run from. Always derive paths from `_ROOT` or a module's `__file__`.

---

## The CHAOS Card Pool

The 50 CHAOS mode cards are defined as a set in `config.py`:

```python
CHAOS_CARDS = { "Electro Spirit", "Ice Spirit", ... }
```

`CHAOS_CARD_LIST = sorted(CHAOS_CARDS)` provides the stable alphabetically-sorted list used for consistent CSV column ordering. **Column order in `output.csv` is determined by this sort — never change it without migrating existing data.**

### Card Data Shape
Cards fetched from the CR API are normalised to:
```python
{
    "id":      int,    # official CR card ID — used in deck deep-links
    "name":    str,
    "elixir":  int,    # elixirCost from API
    "rarity":  str,    # "Common" | "Rare" | "Epic" | "Legendary" | "Champion"
    "type":    str,    # raw type string from CR API (not used for display)
    "iconUrl": str,    # medium icon URL from CR API
}
```

---

## Draft Flow

### Phases
1. **`setup`** — waiting for `/api/start` to be called
2. **`ban`** — players ban cards in `BAN_SEQUENCE = [1, 2, 2, 1]` order
3. **`pick`** — players pick in snake draft `PICK_SEQUENCE = [1, 2, 2, 1, 1, 2, 2, 1, 1, 2, 2, 1, 1, 2, 2, 1]`
4. **`done`** — all picks complete; winner can be recorded

### Random Pre-bans
At `/api/start`, before the ban phase begins, the server automatically removes:
- 2 cards randomly sampled from `TIER_CARDS["S+"]`
- 1 card randomly sampled from `TIER_CARDS["S"]`

These are added to `state["banned"]` with `"by": "random"`. They are displayed in the UI labelled **"RANDOM"** and stored as `"R"` in the `_BANNED` columns of `output.csv`.

### Deck Deep-Link Format
```
https://link.clashroyale.com/en/?clashroyale://copyDeck?deck={id1};{id2};...&l=Royals&tt=159000000
```
Card IDs are semicolon-separated official CR API integer IDs. The link opens the game on mobile and imports the deck directly.

---

## CR API

- **Base URL:** `https://api.clashroyale.com/v1`
- **Auth:** `Authorization: Bearer {CR_API_TOKEN}` header
- **Token:** loaded from `.env` via `python-dotenv`; get one at https://developer.clashroyale.com — **must whitelist your IP address**
- **Cards endpoint:** `GET /cards?limit=200` — returns all cards; filtered in `fetch_cards()` to CHAOS_CARDS only
- **Card caching:** `state["cards"]` is populated once on startup (or on first `/api/start` call) and reused for the whole session. Restart the server to pick up card pool changes.

---

## CSV Data Format (`data/output.csv`)

Each row represents one completed match. Columns:

| Column | Values | Meaning |
|--------|--------|---------|
| `1st_pick` | player name | player who picked first in PICK_SEQUENCE |
| `2nd_pick` | player name | player who picked second |
| `winner` | player name | |
| `loser` | player name | |
| `{CardName}_W` | `0` or `1` | card was in the winner's deck |
| `{CardName}_L` | `0` or `1` | card was in the loser's deck |
| `{CardName}_BANNED` | `0`, `1`, `-1`, `"R"` | `0` = not banned, `1` = banned by winner, `-1` = banned by loser, `"R"` = random pre-ban |

There are 50 `_W` columns, 50 `_L` columns, and 50 `_BANNED` columns — **154 columns total**. Column order mirrors `CHAOS_CARD_LIST` (alphabetical).

The `data/` directory and CSV header row are auto-created on the first call to `/api/record_winner`.

---

## ELO System

`backend/elo.py` is an external file (not authored in this repo). It must export:
- `calculate_elo(input_csv, output_csv)` — reads match history, writes ELO ratings
- `INPUT_CSV` — path it reads from (should align with `data/output.csv`)
- `OUTPUT_CSV` — path it writes to (should align with `data/elo.csv`)

`_refresh_elo()` in `stats.py` calls `calculate_elo` after every recorded match. If `elo.py` is missing, the app degrades gracefully — ELO ratings default to `ELO_STARTING = 1000` for all players.

`/api/elo` reads the **last row** of `elo.csv` to get current ratings — the assumption is that `elo.py` appends a new row per game with all player ELOs as columns.

---

## Adding / Removing Players

Players are defined in three places — all must be updated together:

1. **`config.py`** — `PLAYERS` list (used by backend stats and ELO routes)
2. **`frontend/templates/index.html`** — the two `<select>` dropdowns and the `const PLAYERS` JS array
3. **`frontend/templates/player_stats.html`** — the `const PLAYERS` JS array used to build the leaderboard

---

## Adding / Removing Cards from the Pool

If the CHAOS mode card pool changes:

1. Update `CHAOS_CARDS` in `config.py`
2. `CHAOS_CARD_LIST` updates automatically (it's just `sorted(CHAOS_CARDS)`)
3. **Existing `output.csv` will be incompatible** — the column set will change. Either migrate the CSV manually or archive it and start fresh.
4. Update the tier assignments in `TIER_CARDS` (config.py) and `CARD_TIER` / `CARD_TYPE` (card_tiers.js / card_types.js) if needed

---

## Frontend Architecture

The frontend is split across two standalone HTML templates in `frontend/templates/`. There is no build step, no bundler, no npm.

### `index.html` — Main draft UI
| JS Variable | Purpose |
|-------------|---------|
| `gState` | Last state snapshot received from the server |
| `rarityFilter` | Active rarity filter button value |
| `sortMode` | `"type"` \| `"tier"` \| `"elixir"` |
| `elixirAsc` | Boolean — sort direction for elixir mode |

### `player_stats.html` — Player leaderboard and detail
A single-page app that handles two views via JS routing (no page reloads):
- **Leaderboard** — all players ranked by ELO, click a row to drill into a player
- **Player detail** — two tabs:
  - **Card Stats tab** — sortable card stats table (pick %, win %, ban %) for that player's games only, using `GET /api/player_stats/<name>`
  - **Recent Matches tab** — last 10 games using `GET /api/match_history/<name>`

Key JS functions:
```
showLeaderboard()         → switch to leaderboard view
showDetail(name)          → switch to player detail, triggers data loads
switchTab('stats'|'history')  → toggle between the two detail tabs
loadLeaderboard()         → fetches /api/player_stats + /api/elo, renders ranked table
loadDetailStats(name)     → fetches /api/player_stats/<name>, renders stat cards + card table
loadDetailHistory(name)   → fetches /api/match_history/<name>, renders game cards
sortCardTable(col, id)    → re-sorts and re-renders the card stats table client-side
```

### Static JS data files
Tier and type data live in `static/` as standalone JS files loaded in both templates.

| File | Globals | Purpose |
|------|---------|---------|
| `static/card_tiers.js` | `CARD_TIER`, `TIER_ORDER`, `TIER_ICONS` | Tier per card (S+ → F), display order, emoji icons |
| `static/card_types.js` | `CARD_TYPE`, `TYPE_ORDER`, `TYPE_ICONS` | Type per card, display order, emoji icons |

Flask serves them from `static_folder="static"` configured in `main.py`.

### Draft state flow
```
startDraft() → POST /api/start → applyState(s)
doAction(id) → POST /api/action → applyState(s)
resetDraft() → POST /api/reset → show setup screen
declareWinner(player) → POST /api/record_winner → show banner
```

`applyState()` is the single function that transitions the draft UI between phases. All render functions (`renderPool`, `renderSidebars`, `renderBanned`, `renderDone`) read from `gState`.

### Timer
A 30-second countdown runs per turn (`TURN_SECONDS = 30`). On expiry, `autoPickRandom()` fires a random pick from the current pool. The timer uses `setInterval` + Web Audio API for tick sounds in the last 10 seconds.

---

## Common Tasks

### Change the draft sequences
Edit `BAN_SEQUENCE` and `PICK_SEQUENCE` in `config.py`. The frontend reads these from the API response (`s.ban_sequence`, `s.pick_sequence`) so no frontend changes are needed.

### Change the timer duration
Edit `TURN_SECONDS` in `frontend/templates/index.html` (JS constant, line ~`const TURN_SECONDS = 30`).

### Change random pre-ban counts or tiers
Edit the `random.sample(splus_pool, ...)` call in `start_draft()` in `backend/draft.py`, and update `TIER_CARDS` in `config.py` to change which cards are eligible.

### Add a new API route
1. Decide which Blueprint it belongs to (`draft_bp` for draft logic, `stats_bp` for data/history)
2. Add the route function to the relevant file in `backend/`
3. No registration needed — Blueprints are already registered in `main.py`

### Change the port
Edit `PORT` in `config.py`.

### Update card tier assignments
Edit `static/card_tiers.js` — move card names between tier arrays in the `tiers` object. `TIER_ORDER` and `TIER_ICONS` only need changing if you add or remove a tier entirely.

### Update card type assignments
Edit `static/card_types.js` — change the value for any card name in `CARD_TYPE`. `TYPE_ORDER` controls the display order of groups; `TYPE_ICONS` controls the emoji shown next to each group header.

---

## What Not To Do

- **Don't use relative paths for data files.** Always anchor to `_ROOT` from `config.py`.
- **Don't modify `CHAOS_CARD_LIST` ordering.** The CSV column layout depends on it being `sorted(CHAOS_CARDS)`.
- **Don't add a second global state dict.** All draft state flows through `state` in `backend/draft.py`. `stats.py` imports it directly.
- **Don't add a templating engine or build step** to the frontend without significant justification — the single-file approach is intentional for portability.
- **Don't inline tier or type data back into `index.html`.** They live in `static/card_tiers.js` and `static/card_types.js` precisely so they can be edited without touching the main template.
- **Don't commit `.env`.** It contains the CR API token and a whitelisted IP.