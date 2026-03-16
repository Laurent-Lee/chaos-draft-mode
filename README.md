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
│   ├── stats.py         # CSV recording, match history, card/player stats, ELO
│   └── elo.py           # ELO calculator (bring your own, see Setup)
│
├── frontend/
│   ├── frontend.py      # Blueprint serving the HTML frontend and stats page
│   ├── stats.html       # Card stats page (bring your own, see Setup)
│   └── templates/
│       ├── index.html        # Main draft UI
│       └── player_stats.html # Player leaderboard + per-player detail page
│
├── static/
│   ├── elixir.svg       # Elixir icon used in the UI
│   ├── card_tiers.js    # Card tier assignments (S+/S/A/B/C/D/F) — edit to update tier list
│   └── card_types.js    # Card type assignments (Tower/Tanks/Ranged/etc) — edit to update types
│
└── data/
    ├── output.csv        # Match history (auto-created on first recorded game)
    └── elo.csv           # ELO ratings (auto-created by elo.py)
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

### 3. Install dependencies

```bash
pip install flask flask-cors requests python-dotenv
```

### 4. Add external files

Place the following files in their expected locations:

| File | Location | Purpose |
|------|----------|---------|
| `elo.py` | `backend/` | ELO calculator — must export `calculate_elo`, `OUTPUT_CSV`, `INPUT_CSV` |
| `stats.html` | `frontend/` | Card stats page, accessible at `/stats` |
| `elixir.svg` | `static/` | Elixir icon shown in the card pool UI |

The following files are already included and can be edited directly:

| File | Location | Purpose |
|------|----------|---------|
| `card_tiers.js` | `static/` | Card tier list (S+ through F) — edit to rebalance tiers |
| `card_types.js` | `static/` | Card type groupings — edit to reclassify cards |

### 5. Run the app

```bash
python main.py
```

The app will open automatically at http://127.0.0.1:5050. Press `Ctrl+C` to stop.

## Draft Format

- **Ban phase** — P1 bans 1 → P2 bans 2 → P1 bans 1 (2 bans each)
- **Random pre-bans** — 2 S+ tier and 1 S tier card are banned randomly before the draft starts
- **Pick phase** — Snake draft, 8 picks each (16 total)
- **Deck import** — A Clash Royale deep-link is generated at the end so each player can tap to import their deck directly into the game

## API Routes

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/api/start` | Start a new draft |
| `GET` | `/api/state` | Get current draft state |
| `POST` | `/api/action` | Ban or pick a card |
| `POST` | `/api/reset` | Reset to setup screen |
| `POST` | `/api/record_winner` | Save match result to CSV |
| `GET` | `/api/match_history` | Recent games (all players) with card thumbnails |
| `GET` | `/api/match_history/<name>` | Recent games for a specific player |
| `GET` | `/api/card_stats` | Per-card win/pick/ban rates (all games) |
| `GET` | `/api/player_stats` | Per-player win/loss counts (all players) |
| `GET` | `/api/player_stats/<name>` | Full stats for one player: ELO, W/L, win%, card stats |
| `GET` | `/api/elo` | Current ELO ratings for all players |

## Pages

| URL | Description |
|-----|-------------|
| `/` | Main draft UI |
| `/player_stats` | Player leaderboard ranked by ELO, click any player for their detail page |
| `/stats` | Card stats page (requires `frontend/stats.html`) |