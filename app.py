"""
FIFA World Cup 2026 Live Dashboard - Backend Proxy
Proxies and normalizes the ESPN scoreboard API.
"""
import os
from datetime import datetime, timezone
from functools import lru_cache

import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"


def _normalize_team(competitor: dict) -> dict:
    team = competitor.get("team", {})
    stats = competitor.get("statistics", [])
    stats_map = {s.get("name"): s.get("displayValue") for s in stats}
    return {
        "id": team.get("id"),
        "name": team.get("displayName"),
        "shortName": team.get("shortDisplayName"),
        "abbreviation": team.get("abbreviation"),
        "logo": team.get("logo"),
        "color": team.get("color"),
        "homeAway": competitor.get("homeAway"),
        "winner": competitor.get("winner"),
        "advance": competitor.get("advance"),
        "score": competitor.get("score"),
        "record": competitor.get("records", [{}])[0].get("summary"),
        "form": competitor.get("form"),
        "stats": {
            "possession": stats_map.get("possessionPct"),
            "shots": stats_map.get("totalShots"),
            "shotsOnTarget": stats_map.get("shotsOnTarget"),
            "corners": stats_map.get("wonCorners"),
            "fouls": stats_map.get("foulsCommitted"),
            "goals": stats_map.get("totalGoals"),
            "assists": stats_map.get("goalAssists"),
        },
    }


def _normalize_goals(details: list) -> list:
    goals = []
    for d in details:
        if not d.get("scoringPlay"):
            continue
        athlete = (d.get("athletesInvolved") or [{}])[0]
        goals.append(
            {
                "teamId": d.get("team", {}).get("id"),
                "minute": d.get("clock", {}).get("displayValue"),
                "type": d.get("type", {}).get("text"),
                "scorer": athlete.get("displayName"),
                "jersey": athlete.get("jersey"),
                "penalty": d.get("penaltyKick", False),
                "ownGoal": d.get("ownGoal", False),
            }
        )
    return goals


def _normalize_cards(details: list) -> list:
    cards = []
    for d in details:
        is_red = d.get("redCard", False)
        is_yellow = d.get("yellowCard", False)
        if not (is_red or is_yellow):
            continue
        athlete = (d.get("athletesInvolved") or [{}])[0]
        cards.append(
            {
                "teamId": d.get("team", {}).get("id"),
                "minute": d.get("clock", {}).get("displayValue"),
                "type": "red" if is_red else "yellow",
                "player": athlete.get("displayName"),
            }
        )
    return cards


def _normalize_match(event: dict) -> dict:
    competition = event.get("competitions", [{}])[0]
    status = competition.get("status", {})
    status_type = status.get("type", {})
    competitors = competition.get("competitors", [])
    teams = [_normalize_team(c) for c in competitors]
    details = competition.get("details", [])

    broadcast_names = []
    for b in competition.get("broadcasts", []):
        broadcast_names.extend(b.get("names", []))

    return {
        "id": event.get("id"),
        "name": event.get("name"),
        "shortName": event.get("shortName"),
        "date": event.get("date"),
        "group": competition.get("altGameNote"),
        "state": status_type.get("state"),  # pre, in, post
        "description": status_type.get("description"),
        "detail": status.get("detail"),
        "shortDetail": status.get("shortDetail"),
        "completed": status_type.get("completed", False),
        "period": status.get("period"),
        "clock": status.get("displayClock"),
        "attendance": competition.get("attendance"),
        "venue": competition.get("venue", {}).get("fullName"),
        "venueCity": competition.get("venue", {}).get("address", {}).get("city"),
        "broadcasts": list(set(broadcast_names)),
        "teams": teams,
        "goals": _normalize_goals(details),
        "cards": _normalize_cards(details),
        "links": {link.get("text"): link.get("href") for link in event.get("links", [])},
    }


def _normalize_payload(data: dict) -> dict:
    league = (data.get("leagues") or [{}])[0]
    return {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "day": data.get("day", {}).get("date"),
        "tournament": league.get("name"),
        "season": league.get("season", {}).get("displayName"),
        "matches": [_normalize_match(e) for e in data.get("events", [])],
    }


def _fetch_scoreboard(date: str | None = None) -> dict:
    params = {}
    if date:
        params["date"] = date
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    resp = requests.get(ESPN_URL, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    return _normalize_payload(resp.json())


def _get_scoreboard(date: str | None = None) -> dict:
    return _fetch_scoreboard(date)


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/scoreboard")
def scoreboard():
    date = request.args.get("date")
    try:
        data = _get_scoreboard(date)
        response = jsonify(data)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except requests.RequestException as exc:
        return jsonify({"error": "Failed to fetch ESPN data", "detail": str(exc)}), 502
    except Exception as exc:
        return jsonify({"error": "Internal error", "detail": str(exc)}), 500


@app.route("/api/health")
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
