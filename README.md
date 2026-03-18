# ⚔️ CR Draft — Clash Royale CHAOS Mode Draft Tool 

A local web app for running a ban/pick draft between two players using the official CHAOS mode card pool.

## File Structure

```
cr_draft/
├── main.py              # Entry point — Flask app, Blueprint registration, startup
├── config.py            # All constants (card pool, sequences, player names, paths)
├── README.md
├── .env                 # Your CR API token (not committed to git)
│
├── backend/
│   ├── cards.py         # CR API fetching and deck link generation
│   ├── draft.py         # Draft state, game logic, and draft API routes
│   ├── modifiers.py     # Modifier name mapping and modifiers_data.csv aggregation
│   ├── stats.py          # CSV recording, match history, card/player stats, ELO
│   ├── elo.py            # ELO calculator — exports calculate_elo, OUTPUT_CSV, INPUT_CSV
│   ├── ai_draft.py       # AI draft logic — Ollama integration, context filtering, prompt builder
│   ├── get_card_data.py  # Card/matchup stat readers used by AI draft
│   └── tier_calculator.py # Bayesian rating calculator — appends ratings to card_data.csv
│
├── frontend/             # Legacy Flask/Jinja2 templates (superseded by react-frontend)
│   ├── frontend.py      # Blueprint — still serves /elixir.svg and legacy routes
│   ├── stats.html       # Legacy card stats page
│   └── templates/
│       ├── index.html        # Legacy main draft UI
│       ├── card_detail.html  # Legacy card detail page
│       └── player_stats.html # Legacy player leaderboard
│
├── react-frontend/       # ✅ Active frontend — Vite + React (runs on :5173)
│   ├── package.json      # Dependencies: react, react-router-dom, qrcode.react, vite, tailwindcss
│   ├── vite.config.js    # Proxies /api/* and /elixir.svg to Flask on :5050
│   ├── index.html        # HTML entry point (loads Google Fonts)
│   └── src/
│       ├── main.jsx          # React entry point
│       ├── App.jsx           # React Router — 5 routes
│       ├── styles/
│       │   └── theme.css     # Design system CSS (tokens, components, page styles)
│       ├── data/
│       │   ├── cardTiers.js  # CARD_TIER, TIER_ORDER, TIER_ICONS (mirrors static/card_tiers.js)
│       │   ├── cardTypes.js  # CARD_TYPE, TYPE_ORDER, TYPE_ICONS (mirrors static/card_types.js)
│       │   ├── tierColors.js # Tier → hex color + glow for CSS variable theming
│       │   └── players.js    # PLAYERS list
│       └── pages/
│           ├── DraftPage.jsx       # Main draft UI: setup → ban/pick → done
│           ├── PlayerStatsPage.jsx # ELO leaderboard + per-player detail tabs
│           ├── CardDetailPage.jsx  # Per-card profile + matchup table
│           ├── CardStatsPage.jsx   # Card stats table with filters
│           └── LandingPage.jsx     # Dashboard overview (stats, leaderboard, recent matches)
│
├── static/
│   ├── elixir.svg       # Elixir icon used in the UI
│   ├── card_tiers.js    # Card tier assignments (S+/S/A/B/C/D/F) — edit to update tier list
│   └── card_types.js    # Card type assignments (Tower/Tanks/Ranged/etc) — edit to update types
│
└── data/
    ├── output.csv             # Match history — 166 columns (auto-created on first game)
    ├── modifiers_data.csv     # Modifier aggregate stats — auto-updated after each match
    ├── card_data.csv          # Card matchup matrix + Bayesian ratings — auto-updated after each match
    ├── elo.csv                # ELO ratings — written by elo.py after each match
    ├── player_tags.json       # App player name → CR player tag mapping
    └── backfill_modifiers.py  # One-off script to populate modifier data for old rows
```

## Setup

### 1. Get a CR API Token

- Go to https://developer.clashroyale.com
- Create an account and register a new app
- Whitelist your current IP address
- Copy your API token

### 2. Create a `.env` file

In the project root (`cr_draft/`), create a `.env` file:

```
CR_API_TOKEN=your_token_here
```

### 3. Install Python dependencies

```bash
pip install flask flask-cors requests python-dotenv ollama
```

### 4. Install Node.js (for the React frontend)

```bash
brew install node   # macOS — or download from https://nodejs.org
```

### 5. Install React frontend dependencies

```bash
cd react-frontend
npm install
```

### 6. Add external files

Place the following file in its expected location:

| File | Location | Purpose |
|------|----------|---------|
| `elixir.svg` | `static/` | Elixir icon shown in the card pool UI |

The following files are already included and can be edited directly:

| File | Location | Purpose |
|------|----------|---------|
| `elo.py` | `backend/` | ELO calculator |
| `card_tiers.js` | `static/` | Card tier list (S+ through F) — edit to rebalance tiers |
| `card_types.js` | `static/` | Card type groupings — edit to reclassify cards |

### 7. Run the app

Start the Flask backend:

```bash
python main.py
```

In a separate terminal, start the React dev server:

```bash
cd react-frontend
npm run dev
```

Open **http://localhost:5173** in your browser. The React app proxies all `/api/*` calls to Flask on `:5050` automatically. Press `Ctrl+C` in each terminal to stop.

## AI Draft Mode

Click **🤖 AI Draft** on the setup screen to let Ollama draft both teams automatically. The AI bans and picks using:
- **Bayesian-adjusted overall ratings** from `data/card_data.csv` (computed by `tier_calculator.py` after each game)
- **Head-to-head matchup ratings** to select counters to opponent picks
- **Type-relative win rate deltas** and local tier labels to correct for the LLM's own Clash Royale priors
- **Context filtering** — only the top-10 rated cards plus best counters are shown each turn (not all 50)

You can still record a winner at the end.

**Requirements:**
1. Install Ollama: https://ollama.com
2. Pull a model: `ollama pull llama3.2`

If Ollama is not running, the AI falls back to picking the highest win-rate card — the draft always completes.

To change the model, edit `OLLAMA_MODEL` in `config.py`.

> **Note:** `data/modifiers_data.csv` is not currently reliable — the CR API modifier matching is incomplete. Do not use it as a data source until the matching logic is fixed.

## Draft Format

- **Ban phase** — P1 bans 1 → P2 bans 2 → P1 bans 1 (2 bans each)
- **Random pre-bans** — 2 S+ tier and 1 S tier card are banned randomly before the draft starts
- **Pick phase** — Snake draft, 8 picks each (16 total)
- **Deck import** — A Clash Royale deep-link is generated at the end so each player can tap to import their deck directly into the game

## API Routes

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/api/start` | Start a new draft (`ai_mode: true` for AI draft) |
| `GET` | `/api/state` | Get current draft state |
| `POST` | `/api/action` | Ban or pick a card |
| `POST` | `/api/reset` | Reset to setup screen |
| `POST` | `/api/ai_action` | Trigger one AI ban/pick (used automatically by AI Draft mode) |
| `POST` | `/api/record_winner` | Save match result to CSV |
| `GET` | `/api/match_history` | Recent games (all players) with card thumbnails |
| `GET` | `/api/match_history/<name>` | Recent games for a specific player |
| `GET` | `/api/card_stats` | Per-card win/pick/ban rates (all games) |
| `GET` | `/api/player_stats` | Per-player win/loss counts (all players) |
| `GET` | `/api/player_stats/<name>` | Full stats for one player: ELO, W/L, win%, card stats |
| `GET` | `/api/elo` | Current ELO ratings for all players |

## Pages

All pages are served by the React frontend at `http://localhost:5173`.

| URL | Page | Description |
|-----|------|-------------|
| `/` | DraftPage | Setup screen → ban/pick draft → done screen with deck links |
| `/player_stats` | PlayerStatsPage | ELO leaderboard, click any player for their Card Stats + Recent Matches tabs |
| `/card/:cardName` | CardDetailPage | Per-card profile with tier-color theming and head-to-head matchup table |
| `/stats` | CardStatsPage | Card stats table with tier/type/mode filters, search, and CSV export |
| `/dashboard` | LandingPage | Overview dashboard — summary stats, top cards, leaderboard, recent matches |

## Merging Data from Multiple Machines

Each game recorded by the app includes a `timestamp` column in `output.csv` (ISO 8601 UTC, e.g. `2026-03-16T14:32:05Z`). Both `stats.py` and `backend/elo.py` sort by this column before processing, so ELO is always calculated in true chronological order regardless of row position in the file.

To combine two CSV files from different machines:

```bash
# Keep the header from one file, strip it from the other, then concatenate
head -1 machine_a.csv > combined.csv
tail -n +2 machine_a.csv >> combined.csv
tail -n +2 machine_b.csv >> combined.csv
```

Replace `data/output.csv` with `combined.csv` and restart the app. No further sorting is needed — the app handles it automatically.

**Notes:**
- Old rows recorded before the timestamp column was added have an empty `timestamp` cell. They sort to the top and are treated as the oldest games, which is the safest assumption.
- Do not manually reorder rows or strip the header — the column order in `output.csv` is fixed and must not change.
