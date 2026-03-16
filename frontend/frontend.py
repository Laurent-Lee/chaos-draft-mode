"""
frontend.py — Blueprint that serves the frontend HTML and static assets.

Routes:
  GET /              → renders frontend/templates/index.html
  GET /elixir.svg    → serves static/elixir.svg
  GET /stats         → serves frontend/stats.html
  GET /player_stats  → renders frontend/templates/player_stats.html
"""

import os
from flask import Blueprint, render_template, send_file

_HERE    = os.path.dirname(os.path.abspath(__file__))
_ROOT    = os.path.dirname(_HERE)

frontend_bp = Blueprint(
    "frontend",
    __name__,
    template_folder=os.path.join(_HERE, "templates"),
)


@frontend_bp.route("/")
def index():
    return render_template("index.html")


@frontend_bp.route("/elixir.svg")
def elixir_svg():
    svg_path = os.path.join(_ROOT, "static", "elixir.svg")
    if os.path.exists(svg_path):
        return send_file(svg_path, mimetype="image/svg+xml")
    return "", 404


@frontend_bp.route("/player_stats")
def player_stats_page():
    return render_template("player_stats.html")


@frontend_bp.route("/stats")
def stats_page():
    stats_path = os.path.join(_HERE, "stats.html")
    if os.path.exists(stats_path):
        with open(stats_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>stats.html not found — place it in the frontend/ folder</h1>", 404