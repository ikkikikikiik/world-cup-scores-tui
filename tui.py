"""
FIFA World Cup 2026 Live TUI
A discreet terminal dashboard for live matches.
"""
from datetime import datetime, timedelta, timezone

import requests
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Footer, Header, Label, Static

ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
REFRESH_SECONDS = 15
TOURNAMENT_END_DATE = "20260719"


def _scoreboard_url() -> str:
    """Build a scoreboard URL that includes future matches."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=3)).strftime("%Y%m%d")
    return f"{ESPN_URL}?dates={start}-{TOURNAMENT_END_DATE}"


def _normalize_team(competitor: dict) -> dict:
    team = competitor.get("team", {})
    stats = competitor.get("statistics", [])
    stats_map = {s.get("name"): s.get("displayValue") for s in stats}
    return {
        "id": team.get("id"),
        "name": team.get("displayName"),
        "shortName": team.get("shortDisplayName"),
        "abbreviation": team.get("abbreviation"),
        "homeAway": competitor.get("homeAway"),
        "score": competitor.get("score"),
        "form": competitor.get("form", ""),
        "stats": {
            "possession": stats_map.get("possessionPct"),
            "shots": stats_map.get("totalShots"),
            "shotsOnTarget": stats_map.get("shotsOnTarget"),
            "corners": stats_map.get("wonCorners"),
            "fouls": stats_map.get("foulsCommitted"),
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
                "scorer": athlete.get("displayName"),
                "penalty": d.get("penaltyKick", False),
                "ownGoal": d.get("ownGoal", False),
            }
        )
    return goals


def _short_group(group: str | None) -> str:
    if not group:
        return ""
    if "Group" in group:
        suffix = group.split("Group")[-1].strip()
        return f"Group {suffix}" if suffix else group
    return group


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
        "group": _short_group(competition.get("altGameNote")),
        "state": status_type.get("state"),
        "clock": status.get("displayClock"),
        "shortDetail": status.get("shortDetail"),
        "completed": status_type.get("completed", False),
        "period": status.get("period"),
        "venue": competition.get("venue", {}).get("fullName"),
        "venueCity": competition.get("venue", {}).get("address", {}).get("city"),
        "broadcasts": list(set(broadcast_names)),
        "teams": teams,
        "goals": _normalize_goals(details),
    }


def fetch_scoreboard() -> dict:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    resp = requests.get(_scoreboard_url(), headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "matches": [_normalize_match(e) for e in data.get("events", [])],
    }


def _format_time(iso_string: str) -> str:
    if not iso_string:
        return ""
    dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    return dt.astimezone().strftime("%a, %b %d, %I:%M %p %Z")


def _find_next_match(matches: list) -> dict | None:
    """Return the earliest match whose kickoff is in the future."""
    now = datetime.now(timezone.utc)
    future = []
    for m in matches:
        date = m.get("date")
        if not date:
            continue
        try:
            dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if dt > now:
            future.append(m)
    if not future:
        return None
    return min(future, key=lambda m: m["date"])


def _countdown_to(iso_string: str) -> str:
    """Return a human-readable countdown to the given ISO datetime."""
    if not iso_string:
        return ""
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return ""
    now = datetime.now(timezone.utc)
    if dt <= now:
        return "starting now"
    delta = dt - now
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


class MatchCard(Static):
    """A live match card styled like the web dashboard."""

    def __init__(self, match: dict, **kwargs):
        super().__init__(**kwargs)
        self.match = match

    def compose(self) -> ComposeResult:
        home = next(t for t in self.match["teams"] if t["homeAway"] == "home")
        away = next(t for t in self.match["teams"] if t["homeAway"] == "away")
        home_goals = [g for g in self.match["goals"] if g["teamId"] == home["id"]]
        away_goals = [g for g in self.match["goals"] if g["teamId"] == away["id"]]
        venue = self.match.get("venue") or ""
        city = self.match.get("venueCity") or ""
        broadcasts = self.match.get("broadcasts", [])

        with Vertical(classes="match-card"):
            # Header: live badge + date | group
            with Horizontal(classes="match-header"):
                with Horizontal(classes="header-left"):
                    yield Label(f"● LIVE {self.match['clock'] or ''}", classes="live-badge")
                    yield Label(_format_time(self.match.get("date", "")), classes="match-time")
                yield Label(self.match.get("group", ""), classes="match-group")

            # Main scoreboard: home | center | away
            with Horizontal(classes="scoreboard"):
                with Vertical(classes="team-col home-col"):
                    yield Label(home["name"], classes="team-name")
                    yield Label(home.get("form", ""), classes="team-form")
                    yield Label(str(home["score"]), classes="big-score")
                    yield Label(self._goals_text(home_goals, home["abbreviation"]), classes="scorers")
                with Vertical(classes="center-col"):
                    yield Label("vs", classes="vs-badge")
                with Vertical(classes="team-col away-col"):
                    yield Label(away["name"], classes="team-name")
                    yield Label(away.get("form", ""), classes="team-form")
                    yield Label(str(away["score"]), classes="big-score")
                    yield Label(self._goals_text(away_goals, away["abbreviation"]), classes="scorers")

            # Stats table
            yield from self._render_stats(home, away)

            # Footer: venue | broadcasts
            with Horizontal(classes="match-footer"):
                venue_text = f"🏟 {venue}" + (f", {city}" if city else "")
                yield Label(venue_text, classes="venue")
                yield Label(f"📺 {', '.join(broadcasts)}" if broadcasts else "", classes="broadcasts")

    def _goals_text(self, goals: list, abbr: str) -> str:
        if not goals:
            return ""
        lines = []
        for g in goals:
            icon = "⚽"
            suffix = "(P)" if g["penalty"] else "(OG)" if g["ownGoal"] else f"({abbr})"
            lines.append(f"{icon} {g['scorer']} {suffix} {g['minute']}")
        return "\n".join(lines)

    def _render_stats(self, home: dict, away: dict) -> ComposeResult:
        hs = home.get("stats", {})
        aw = away.get("stats", {})
        stats = [
            ("Possession", hs.get("possession"), aw.get("possession"), "%"),
            ("Shots", hs.get("shots"), aw.get("shots"), ""),
            ("On Target", hs.get("shotsOnTarget"), aw.get("shotsOnTarget"), ""),
            ("Corners", hs.get("corners"), aw.get("corners"), ""),
            ("Fouls", hs.get("fouls"), aw.get("fouls"), ""),
        ]
        for label, h_val, a_val, suffix in stats:
            if h_val is None or a_val is None:
                continue
            with Horizontal(classes="stat-row"):
                yield Label(f"{h_val}{suffix}", classes="stat-home")
                yield Label(label, classes="stat-label")
                yield Label(f"{a_val}{suffix}", classes="stat-away")


class WorldCupTUI(App):
    """Terminal dashboard for live FIFA World Cup 2026 matches."""

    CSS = """
    Screen {
        align: center top;
    }
    #main {
        width: 100%;
        height: 100%;
        padding: 1 2;
    }
    #status {
        dock: top;
        height: 1;
        content-align: center middle;
        color: $text-muted;
    }
    #empty {
        width: 100%;
        height: 100%;
        content-align: center middle;
        color: $text-muted;
    }
    .match-card {
        width: 100%;
        height: auto;
        border: solid $primary;
        padding: 1 2;
        margin: 1 0;
    }
    .match-header {
        width: 100%;
        height: auto;
    }
    .header-left {
        width: auto;
        height: auto;
    }
    .live-badge {
        width: auto;
        color: $error;
        text-style: bold;
    }
    .match-time {
        width: auto;
        padding-left: 2;
        color: $text-muted;
    }
    .match-group {
        width: 1fr;
        text-align: right;
        color: $warning;
    }
    .scoreboard {
        width: 100%;
        height: auto;
        align: center middle;
        margin: 1 0;
    }
    .team-col {
        width: 2fr;
        height: auto;
    }
    .home-col {
        content-align: right middle;
        padding-right: 3;
    }
    .away-col {
        content-align: left middle;
        padding-left: 3;
    }
    .team-name {
        text-style: bold;
    }
    .team-form {
        color: $text-muted;
        text-style: dim;
    }
    .big-score {
        text-style: bold;
        text-align: center;
        color: $success;
        padding: 1 0;
    }
    .home-col .big-score {
        text-align: right;
    }
    .away-col .big-score {
        text-align: left;
    }
    .scorers {
        color: $text-muted;
        text-style: dim;
    }
    .center-col {
        width: 1fr;
        height: auto;
        content-align: center middle;
    }
    .vs-badge {
        width: auto;
        padding: 0 1;
        color: $text;
        background: $surface-lighten-1;
        text-style: bold;
    }
    .stat-row {
        width: 100%;
        height: auto;
        padding: 0 1;
    }
    .stat-home {
        width: 1fr;
        text-align: left;
    }
    .stat-label {
        width: 1fr;
        text-align: center;
        color: $text-muted;
    }
    .stat-away {
        width: 1fr;
        text-align: right;
    }
    .match-footer {
        width: 100%;
        height: auto;
        margin-top: 1;
        padding-top: 1;
    }
    .venue {
        width: 1fr;
        text-align: left;
        color: $text-muted;
    }
    .broadcasts {
        width: 1fr;
        text-align: right;
        color: $text-muted;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
    ]

    matches = reactive(list)
    last_updated = reactive("")
    error_message = reactive("")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main"):
            yield Label("Loading live matches...", id="status")
            yield VerticalScroll(id="match-list")
            yield Label("", id="empty", classes="hidden")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "FIFA World Cup 2026 — Live"
        self.sub_title = "Press R to refresh, Q to quit"
        self._next_match = None
        self.action_refresh()
        self.set_interval(REFRESH_SECONDS, self.action_refresh)
        self.set_interval(1, self._update_countdown)

    def watch_matches(self, matches: list) -> None:
        scroll = self.query_one("#match-list", VerticalScroll)
        scroll.remove_children()
        empty = self.query_one("#empty", Label)

        live = [m for m in matches if m.get("state") == "in"]
        if not live:
            self._next_match = _find_next_match(matches)
            empty.update(self._next_match_text())
            empty.styles.display = "block"
            return

        self._next_match = None
        empty.styles.display = "none"
        for match in live:
            scroll.mount(MatchCard(match))

    def _next_match_text(self) -> str:
        if not self._next_match:
            return "No live matches right now.\nPress R to refresh."
        home = next((t for t in self._next_match["teams"] if t["homeAway"] == "home"), {})
        away = next((t for t in self._next_match["teams"] if t["homeAway"] == "away"), {})
        home_name = home.get("name", "TBD")
        away_name = away.get("name", "TBD")
        match_time = _format_time(self._next_match.get("date", ""))
        countdown = _countdown_to(self._next_match.get("date", ""))
        return (
            f"No live matches right now.\n"
            f"Next match: {home_name} vs {away_name} — {match_time}\n"
            f"Starts in: {countdown}\n"
            f"Press R to refresh."
        )

    def _update_countdown(self) -> None:
        if not self._next_match:
            return
        empty = self.query_one("#empty", Label)
        empty.update(self._next_match_text())

    def watch_last_updated(self, value: str) -> None:
        self.query_one("#status", Label).update(value)

    def watch_error_message(self, value: str) -> None:
        if value:
            self.query_one("#status", Label).update(f"Error: {value}")

    def action_refresh(self) -> None:
        try:
            data = fetch_scoreboard()
            self.matches = data["matches"]
            self.last_updated = f"Updated: {datetime.now().strftime('%H:%M:%S')} | Live matches: {len([m for m in self.matches if m.get('state') == 'in'])}"
            self.error_message = ""
        except Exception as exc:
            self.error_message = str(exc)


if __name__ == "__main__":
    app = WorldCupTUI()
    app.run()
