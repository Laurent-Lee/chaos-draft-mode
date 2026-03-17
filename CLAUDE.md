# CLAUDE.md — CHAOS Mode Draft Codebase Guide

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
│   ├── cards.py          # CR API fetch + deck link generation
│   ├── draft.py          # Global state dict, draft logic, draft API Blueprint
│   ├── modifiers.py      # Modifier name mapping and modifiers_data.csv aggregation
│   ├── stats.py          # CSV I/O, match history, card/player stats, ELO Blueprint
│   ├── elo.py            # ELO calculator — exports calculate_elo, OUTPUT_CSV, INPUT_CSV
│   ├── ai_draft.py       # AI draft logic — Ollama integration, context filtering, prompt builder
│   ├── get_card_data.py  # Card/matchup stat readers — get_card_win_rates, get_matchup_win_rates, get_card_type_relative_win_rates, get_overall_ratings
│   └── tier_calculator.py # Bayesian rating calculator — appends card_1_overall_rating and card_1_matchup_rating to card_data.csv
│
├── frontend/
│   ├── frontend.py      # Frontend Blueprint — serves /, /player_stats, /card/<n>, /elixir.svg, /stats
│   ├── stats.html       # Card stats page (external, served at /stats)
│   └── templates/
│       ├── index.html        # Main draft UI
│       ├── player_stats.html # Player leaderboard + per-player detail (Stats + Recent Matches tabs)
│       └── card_detail.html  # Per-card profile page — stats + head-to-head matchup table
│
├── static/
│   ├── elixir.svg       # Elixir icon served at /elixir.svg via frontend Blueprint
│   ├── card_tiers.js    # CARD_TIER, TIER_ORDER, TIER_ICONS — edit to rebalance tiers
│   └── card_types.js    # CARD_TYPE, TYPE_ORDER, TYPE_ICONS — edit to reclassify cards
│
└── data/
    ├── output.csv             # Match history — 165 columns, auto-created on first recorded game
    ├── modifiers_data.csv     # Modifier aggregate stats — rewritten after each match
    ├── card_data.csv          # Card matchup matrix — 2500 rows + 2 rating columns, rewritten after each match
    ├── elo.csv                # ELO ratings — written by elo.py after each match
    ├── player_tags.json       # App player name → CR player tag (#TAG) mapping
    └── backfill_modifiers.py  # One-off script: populate modifier data for old output.csv rows
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
| `game_mode` | `"Normal Draft"` or `"AI Draft"` | draft mode used; empty on rows predating this column |
| `timestamp` | ISO 8601 UTC string e.g. `2026-03-16T14:32:05Z` | when the match was recorded; empty on rows predating this column |
| `1st_pick` | player name | player who picked first in PICK_SEQUENCE |
| `2nd_pick` | player name | player who picked second |
| `winner` | player name | |
| `loser` | player name | |
| `{CardName}_W` | `0` or `1` | card was in the winner's deck |
| `{CardName}_L` | `0` or `1` | card was in the loser's deck |
| `{CardName}_BANNED` | `0`, `1`, `-1`, `"R"` | `0` = not banned, `1` = banned by winner, `-1` = banned by loser, `"R"` = random pre-ban |
| `Modifier_1_W` … `Modifier_5_W` | internal modifier string e.g. `"Poison3"` | winner's modifiers in pick order; empty if game not yet matched from CR API |
| `Modifier_1_L` … `Modifier_5_L` | internal modifier string | loser's modifiers in pick order |

There are 50 `_W` columns, 50 `_L` columns, 50 `_BANNED` columns, and 10 modifier columns — **166 columns total** (including `game_mode`). Column order mirrors `CHAOS_CARD_LIST` (alphabetical) for the card columns.

The `data/` directory and CSV header row are auto-created on the first call to `/api/record_winner`. Existing CSVs with only 155 columns are automatically migrated to 165 columns on the next recorded match.

Both `stats.py` and `elo.py` sort rows by `timestamp` before processing, so concatenated files from multiple machines are always handled in true chronological order. Rows with an empty `timestamp` sort to the top and are treated as the oldest games.

---

## ⚠️ Known Issue: Modifier Data Not Reliable

`data/modifiers_data.csv` is currently **not reliable**. The CR API modifier matching logic in `backend/stats.py` (`_fetch_battle_modifiers`) is incomplete and frequently fails to find the matching battle, leaving modifier columns empty. Do **not** use `modifiers_data.csv` as a data source for AI or analysis until the matching logic is fixed.

---

## AI Draft Mode

The app supports an **AI Draft Mode** where Ollama (a free local LLM runner) drafts both teams automatically. This uses the `backend/ai_draft.py` module and the `/api/ai_action` route in `backend/draft.py`.

### Setup

1. Install Ollama: https://ollama.com
2. Pull a model: `ollama pull llama3.2`
3. Install the Python package: `pip install ollama`

### Usage

Click **🤖 AI Draft** on the setup screen. The draft runs automatically — the AI bans and picks for both teams based on historical win rates from `data/output.csv`. You can still record a winner at the end as normal.

### Configuration

Change the model in `config.py`:

```python
OLLAMA_MODEL = "llama3.2"   # or "qwen2.5:3b" for faster/smaller
```

### Graceful fallback

If Ollama is not running or `ollama` is not installed, the AI falls back to picking the highest win-rate card available in the pool. The draft always completes.

### Key files

| File | Purpose |
|------|---------|
| `backend/ai_draft.py` | `ai_decide()` calls Ollama and returns `(card_id, reason)`; `build_prompt()` formats the LLM prompt with filtered context; `_select_ai_context()` filters the card pool to a high-signal subset |
| `backend/get_card_data.py` | `get_card_win_rates()`, `get_matchup_win_rates()`, `get_card_type_relative_win_rates()`, `get_overall_ratings()` — all card/matchup stat readers |
| `backend/tier_calculator.py` | `calculate_ratings(card_data_csv, output_csv)` — appends `card_1_overall_rating` and `card_1_matchup_rating` to `card_data.csv` using Bayesian formula |
| `config.py` | `OLLAMA_MODEL` — change to swap the model |
| `backend/draft.py` | `POST /api/ai_action` — triggers one AI turn; `ai_mode` and `ai_log` in state |
| `frontend/templates/index.html` | `startAiDraft()`, `triggerAiIfNeeded()`, `showAiThinking()`, `renderAiLog()` — auto-loop, overlay, and chat panel |

### AI context filtering

`_select_ai_context()` in `ai_draft.py` limits which pool cards are shown to the LLM each turn:
1. **Top counter per opponent pick** — for each card the opponent has picked, find the pool card with the highest `matchup_rating` against it
2. **Top 10 by overall rating** — remaining pool cards sorted by `overall_ratings` descending

This keeps the LLM focused on relevant options rather than all 50 pool cards, reducing hallucinations.

### Bayesian rating formula

```
confidence = ((n + 3) / (n + 4))^2
rating     = confidence * max(win_rate, 0.35) + (1 - confidence) * 0.5
```
- `n == 0` → returns `0.5625` (optimistic prior)
- `n > 0` → blends actual win rate (floored at 0.35) with a 0.5 neutral prior weighted by confidence
- At n → ∞ with 0% win rate, rating converges to 0.35 (the floor)

`card_1_overall_rating`: n = card's total games across all matches; win rate = card's overall win rate
`card_1_matchup_rating`: n = games played for the specific (card_1, card_2) pair; win rate = matchup win rate

---

## Card Matchup Data (`data/card_data.csv`)

2500 rows (50×50 card pairs). Rewritten by `_write_matchups_csv()` in `stats.py` after every recorded match. `tier_calculator.py` then appends two Bayesian rating columns.

| Column | Description |
|--------|-------------|
| `card_1` / `card_2` | Card names for this pair |
| `Games Played` | Head-to-head games where both cards appeared on opposing sides |
| `card_1 Wins` / `card_2 Wins` | Win counts |
| `card_1_matchup_winrate` | `card_1 Wins / Games Played`; empty if 0 games |
| `card_1_overall_rating` | Bayesian-adjusted overall win rate for card_1 (same value on every row for the same card_1) |
| `card_1_matchup_rating` | Bayesian-adjusted matchup win rate for this specific (card_1, card_2) pair |

---

## Modifier Data (`data/modifiers_data.csv`)

Aggregated modifier statistics, rewritten after every match (like `card_data.csv`).

| Column | Meaning |
|--------|---------|
| `modifier_name` | Human-readable display name, e.g. `"Poison III"`, `"Flying Machine I"` |
| `total_games_played` | Games in which this modifier appeared on either side |
| `Modifier_1_W` … `Modifier_5_W` | Times this modifier was at position 1–5 for the **winning** team |
| `Modifier_1_L` … `Modifier_5_L` | Times this modifier was at position 1–5 for the **losing** team |

Each modifier variant (card + tier) is one row. With 50 CHAOS cards × 3 tiers = up to **150 modifier rows**, each with 10 data columns = **1,500 data points** total. The file only contains rows for modifiers observed so far; rows for unseen modifiers are added automatically as new games are recorded.

### Internal → display name mapping
The CR API returns identifiers like `"BlowdartGoblin3"` or `"DartBarrell1"`. These are parsed by `backend/modifiers.py`:
- Base name stripped of trailing digit → looked up in `MODIFIER_BASE_TO_DISPLAY`
- Tier digit converted to Roman numeral (`1`→`I`, `2`→`II`, `3`→`III`)
- Known non-obvious mappings: `BlowdartGoblin` → Dart Goblin, `DartBarrell` → Flying Machine, `AxeMan` → Executioner, `IceSpirits` → Ice Spirit, `Xbow` → X-Bow, `Pekka` → P.E.K.K.A, `Log` → The Log

Add new entries to `MODIFIER_BASE_TO_DISPLAY` in `backend/modifiers.py` as previously unseen modifiers appear.

---

## Player Tag Mapping (`data/player_tags.json`)

Maps each app player name to their Clash Royale player tag. Used by modifier matching to locate the right battle in the CR API battle logs.

```json
{
    "Kevin":   "#JGPUGCUP",
    "Andrew":  "#P2PRRVLP",
    ...
}
```

Update this file when players join or change accounts. The backfill script and `record_winner` both read from this file at runtime.

---

## Modifier Matching Flow

When `/api/record_winner` is called:
1. Winner and loser card sets are built from the draft state
2. `_fetch_battle_modifiers()` in `stats.py` fetches the winner's CR battle log (falls back to the loser's log if the winner has privacy on)
3. The most recent `Crazy_Arena` battle against the correct opponent whose card sets match exactly and whose crowns confirm the winner is selected
4. Modifier strings are extracted by player tag from the `modifiers` field
5. Values are written to `Modifier_1_W … Modifier_5_W` and `Modifier_1_L … Modifier_5_L` in `output.csv`
6. `modifiers_data.csv` is regenerated via `refresh_modifiers()`

If no matching battle is found (privacy enabled, log rolled off, etc.) the modifier columns are left empty and the match is still recorded normally.

### Backfilling old rows
```bash
python3 data/backfill_modifiers.py
```
Fetches battle logs for all unmatched rows in `output.csv` and regenerates `modifiers_data.csv`.

---

## ELO System

`backend/elo.py` is an external file (not authored in this repo). It must export:
- `calculate_elo(input_csv, output_csv)` — reads match history, writes ELO ratings
- `INPUT_CSV` — path it reads from (should align with `data/output.csv`)
- `OUTPUT_CSV` — path it writes to (should align with `data/elo.csv`)

`_refresh_elo()` in `stats.py` calls `calculate_elo` after every recorded match. If `elo.py` is missing, the app degrades gracefully — ELO ratings default to `ELO_STARTING = 1000` for all players.

`/api/elo` reads the **last row** of `elo.csv` to get current ratings — the assumption is that `elo.py` appends a new row per game with all player ELOs as columns.

`elo.py` sorts rows by `timestamp` before processing so ELO is always calculated in true chronological order, even after CSVs from multiple machines are concatenated.

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

The frontend is split across standalone HTML templates in `frontend/templates/` and one static file in `frontend/`. There is no build step, no bundler, no npm.

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

### `card_detail.html` — Per-card profile page
Served at `/card/<card_name>`. Each card has its own URL (e.g. `/card/Electro Wizard`). Reached by clicking any card row in `stats.html`.

Fetches a single endpoint `GET /api/card_detail/<card_name>` which returns:
- **Overall stats** — play rate, win rate, ban rate, wins, losses, total games
- **49 matchup rows** — from `card_data.csv`, one row per opponent card

The page applies a tier-keyed colour theme (CSS `--tier-color` variable) so each card's profile has a distinct accent colour. The matchup table defaults to a grouped view — Favourable (≥55% WR) / Even (45–55%) / Unfavourable (<45%) — with a toggle to show unseen matchups.

**Important:** `card_tiers.js` and `card_types.js` are the single source of truth for tier and type data. All pages (`index.html`, `player_stats.html`, `stats.html`, `card_detail.html`) load them via `<script src="/static/card_tiers.js">`. `config.py` parses `card_tiers.js` at startup — no inline copies exist anywhere.

### `stats.html` — Card stats overview (static file)
Served at `/stats` directly from `frontend/stats.html` (not a Jinja2 template). Clicking any card row navigates to that card's `/card/<n>` detail page.

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
Edit `static/card_tiers.js` — move card names between tier arrays in the `tiers` object. Also update the inline `CARD_TIER` copy in `frontend/templates/card_detail.html`. `TIER_ORDER` and `TIER_ICONS` only need changing if you add or remove a tier entirely.

### Update card type assignments
Edit `static/card_types.js` — change the value for any card name in `CARD_TYPE`. Also update the inline `CARD_TYPE` copy in `frontend/templates/card_detail.html`. `TYPE_ORDER` controls the display order of groups; `TYPE_ICONS` controls the emoji shown next to each group header.

### Regenerate card_data.csv manually
If you concatenate CSVs from multiple machines and want to regenerate `card_data.csv` before starting the app:
```bash
cd cr_draft
python3 -c "from backend.stats import _write_matchups_csv; _write_matchups_csv()"
```
Alternatively, use the **⬇ Export card_data.csv** button on the `/stats` page once the server is running.

---

## What Not To Do

- **Don't use relative paths for data files.** Always anchor to `_ROOT` from `config.py`.
- **Don't modify `CHAOS_CARD_LIST` ordering.** The CSV column layout depends on it being `sorted(CHAOS_CARDS)`.
- **Don't add a second global state dict.** All draft state flows through `state` in `backend/draft.py`. `stats.py` imports it directly.
- **Don't add a templating engine or build step** to the frontend without significant justification — the single-file approach is intentional for portability.
- **Don't inline tier or type data back into `index.html`.** They live in `static/card_tiers.js` and `static/card_types.js` precisely so they can be edited without touching the main template. `card_detail.html` is the only justified exception because it cannot load static JS files as a Jinja2 template.
- **Don't re-introduce inline tier/type data anywhere.** Edit only `card_tiers.js` / `card_types.js` — all pages and `config.py` read from those files automatically.
- **Don't commit `.env`.** It contains the CR API token and a whitelisted IP.