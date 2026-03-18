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
├── frontend/             # Legacy Flask/Jinja2 templates (kept for reference, superseded by react-frontend)
│   ├── frontend.py      # Frontend Blueprint — still serves /elixir.svg and legacy routes
│   ├── stats.html       # Legacy card stats page
│   └── templates/
│       ├── index.html        # Legacy main draft UI
│       ├── player_stats.html # Legacy player leaderboard
│       └── card_detail.html  # Legacy per-card profile page
│
├── react-frontend/       # ✅ Active frontend — Vite + React app (runs on :5173)
│   ├── package.json      # Dependencies: react, react-router-dom, qrcode.react, vite, tailwindcss
│   ├── vite.config.js    # Proxies /api/* and /elixir.svg to Flask on :5050
│   ├── index.html        # HTML entry point (loads Google Fonts)
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── src/
│       ├── main.jsx          # React entry point — mounts App, imports global CSS
│       ├── App.jsx           # React Router — 5 routes (see Routes section below)
│       ├── index.css         # Tailwind directives (for LandingPage only)
│       ├── styles/
│       │   └── theme.css     # Combined CSS from all 4 ported pages — design tokens, shared components
│       ├── data/
│       │   ├── cardTiers.js  # ES module: CARD_TIER, TIER_ORDER, TIER_ICONS (mirrors static/card_tiers.js)
│       │   ├── cardTypes.js  # ES module: CARD_TYPE, TYPE_ORDER, TYPE_ICONS (mirrors static/card_types.js)
│       │   ├── tierColors.js # Tier → hex color + glow for CSS variable theming
│       │   └── players.js    # PLAYERS list — single source of truth for React frontend
│       └── pages/
│           ├── DraftPage.jsx       # Main draft UI: setup → ban/pick → done (port of index.html)
│           ├── PlayerStatsPage.jsx # Leaderboard + player detail tabs (port of player_stats.html)
│           ├── CardDetailPage.jsx  # Per-card profile + matchup table (port of card_detail.html)
│           ├── CardStatsPage.jsx   # Card stats table with filters (port of stats.html)
│           └── LandingPage.jsx     # Dashboard overview (stats summary, leaderboard, recent matches)
│
├── static/
│   ├── elixir.svg       # Elixir icon served at /elixir.svg via frontend Blueprint
│   ├── card_tiers.js    # CARD_TIER, TIER_ORDER, TIER_ICONS — edit to rebalance tiers (also update react-frontend/src/data/cardTiers.js)
│   └── card_types.js    # CARD_TYPE, TYPE_ORDER, TYPE_ICONS — edit to reclassify cards (also update react-frontend/src/data/cardTypes.js)
│
└── data/
    ├── output.csv             # Match history — 165 columns, auto-created on first recorded game
    ├── modifiers_data.csv     # Modifier aggregate stats — rewritten after each match
    ├── card_data.csv          # Card matchup matrix — 2500 rows + 2 rating columns, rewritten after each match
    ├── elo.csv                # ELO ratings — written by elo.py after each match
    ├── player_tags.json       # App player name → CR player tag (#TAG) mapping
    └── backfill_modifiers.py  # One-off script: populate modifier data for old output.csv rows
```

### React Frontend Routes

| URL | Page | Description |
|-----|------|-------------|
| `/` | `LandingPage` | Dashboard overview (stats, leaderboard, recent matches) + draft setup form |
| `/draft` | `DraftPage` | Ban/pick draft → done screen (draft state passed via navigation state) |
| `/player_stats` | `PlayerStatsPage` | ELO leaderboard + per-player detail (Card Stats + Recent Matches tabs) |
| `/card/:cardName` | `CardDetailPage` | Per-card profile with tier-color theming + matchup table |
| `/stats` | `CardStatsPage` | Card stats table with tier/type/mode filters |

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

The active frontend is a **Vite + React** app in `react-frontend/`. It runs on `:5173` during development and proxies all `/api/*` calls to the Flask server on `:5050`. The legacy Jinja2 templates in `frontend/templates/` are kept for reference but are no longer the primary UI.

### Running the React frontend

```bash
cd react-frontend
npm install   # first time only
npm run dev   # starts Vite dev server at http://localhost:5173
```

Flask (`python main.py`) must also be running on `:5050` for API calls to work.

### React app structure

**`App.jsx`** — React Router with 5 routes. The draft tool is at `/` (root), matching the original Flask URL layout.

**`pages/DraftPage.jsx`** — Port of `index.html`. Receives initial draft state via `location.state.draft` (set by `LandingPage` after calling `/api/start`). Two conditional render blocks driven by `draft.phase`:
- `draft.phase === 'ban' | 'pick'` → Draft screen (pool, sidebars, timer, banned strip)
- `draft.phase === 'done'` → Done screen (deck links, QR codes, winner buttons)

If no draft state is present in navigation state, the page redirects to `/`.

Key state and behavior:
- `draft` — mirrors the API state object from `/api/action`, etc. (initial value from navigation state)
- Timer: 30s countdown using `setInterval` + `useRef` to avoid stale closures; resets on each new turn (when `action_index` changes); auto-picks random card on expire
- Tick sounds: Web Audio API square oscillator (220 Hz normal / 320 Hz urgent), same scheduling logic as original
- AI mode: `useEffect` on `[draft?.action_index, draft?.phase, draft?.ai_mode]` — fires 800ms after each state change, calls `/api/ai_action`, loops by triggering re-render
- Pool rendering: three sort modes (type / tier / elixir), rarity filter, search, same group/label structure as original

**`pages/PlayerStatsPage.jsx`** — Port of `player_stats.html`. React state routing between leaderboard and player detail; tabs implemented with `activeTab` state.

**`pages/CardDetailPage.jsx`** — Port of `card_detail.html`. Gets card name from `useParams()`. Sets `--tier-color` and `--tier-glow` CSS variables via `document.documentElement.style.setProperty` on data load; cleans up on unmount. Stat bars animated with `requestAnimationFrame` + `data-pct` attributes.

**`pages/CardStatsPage.jsx`** — Port of `stats.html`. Tier/type/mode filters, search, sortable table, export button.

**`pages/LandingPage.jsx`** — Dashboard overview with Tailwind CSS (not a port of an existing page). Available at `/dashboard`.

### Data files (`react-frontend/src/data/`)

These are ES module versions of the Flask static JS files. **When updating tiers or types, edit both the `static/` file (for Flask/config.py) and the corresponding `src/data/` file (for React).**

| File | Exports | Mirrors |
|------|---------|---------|
| `cardTiers.js` | `CARD_TIER`, `TIER_ORDER`, `TIER_ICONS` | `static/card_tiers.js` |
| `cardTypes.js` | `CARD_TYPE`, `TYPE_ORDER`, `TYPE_ICONS` | `static/card_types.js` |
| `tierColors.js` | `TIER_COLORS` | tier color theming (was inline in `card_detail.html`) |
| `players.js` | `PLAYERS` | `config.py` `PLAYERS` list |

### CSS

All styles for the four ported pages live in **`react-frontend/src/styles/theme.css`** — a single combined file covering CSS variables (design tokens), shared components (header, buttons, match history cards, mode badges), and page-specific styles. Tailwind (in `index.css`) is used only by `LandingPage.jsx`.

### Draft state flow (React)
```
LandingPage:
  startDraft()    → POST /api/start       → navigate('/draft', { state: { draft: s } })

DraftPage:
  (init)          → location.state.draft  → setDraft(s)
  doAction(cardId)→ POST /api/action      → setDraft(s)
  undoAction()    → POST /api/undo        → setDraft(s)
  resetDraft()    → POST /api/reset       → navigate('/')
  declareWinner(n)→ POST /api/record_winner → setWinnerInfo(res)
```

All state transitions call `setDraft(s)` which triggers re-renders and, in AI mode, re-triggers the AI polling `useEffect`.

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