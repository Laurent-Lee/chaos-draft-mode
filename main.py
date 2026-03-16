"""
Clash Royale Draft Tool
=======================
Run with:  python main.py
Then open: http://127.0.0.1:5050

Setup:
  1. Get a free API token at https://developer.clashroyale.com
     (whitelist your current IP address there)
  2. Add CR_API_TOKEN to a .env file or export it:
       export CR_API_TOKEN=your_token_here
  3. python main.py

Draft format:
  Ban phase  — P1 → P2 → P2 → P1   (2 bans each)
  Pick phase — snake draft, 8 picks each (16 total)

Deck string — generates a https://link.clashroyale.com/deck/en?deck=... link
              using the official card IDs returned by the CR API so you can
              tap it on your phone and import the deck directly into the game.
"""

import threading
import webbrowser

from flask import Flask
from flask_cors import CORS

from config import CR_API_TOKEN, PORT
from cards import fetch_cards
from draft import draft_bp, state
from stats import stats_bp
from frontend import frontend_bp

# ── App factory ───────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates")
CORS(app)

app.register_blueprint(draft_bp)
app.register_blueprint(stats_bp)
app.register_blueprint(frontend_bp)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not CR_API_TOKEN:
        print("\n⚠️  WARNING: CR_API_TOKEN environment variable is not set!")
        print("   Export it before running: export CR_API_TOKEN=your_token_here")
        print("   Get one at: https://developer.clashroyale.com\n")

    # Pre-load card data so match history icons work before any draft is started
    if CR_API_TOKEN and not state["cards"]:
        try:
            print("⏳  Pre-loading card data…")
            state["cards"] = fetch_cards()
            print(f"✅  Loaded {len(state['cards'])} cards.")
        except Exception as e:
            print(f"⚠️  Could not pre-load cards: {e}")

    url = f"http://127.0.0.1:{PORT}"
    print(f"⚔️  CR Draft starting on {url}")
    print("   Press Ctrl+C to stop.\n")

    def open_browser():
        import time
        time.sleep(1.2)
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()

    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
