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


def _sort_matches(matches: list) -> list:
    """Sort matches like the web dashboard: live first, then finished, then upcoming."""
    state_order = {"in": 0, "post": 1, "pre": 2}

    def _key(match: dict):
        state = match.get("state")
        date = match.get("date") or ""
        try:
            ts = datetime.fromisoformat(date.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.min.replace(tzinfo=timezone.utc)
        # Within finished: most recent first; otherwise earliest first.
        sort_ts = -ts.timestamp() if state == "post" else ts.timestamp()
        return (state_order.get(state, 3), sort_ts)

    return sorted(matches, key=_key)


class MatchCard(Static):
    """A match card styled like the web dashboard."""

    def __init__(self, match: dict, **kwargs):
        super().__init__(**kwargs)
        self.match = match

    def _state_badge(self) -> str:
        state = self.match.get("state")
        if state == "in":
            return f"● LIVE {self.match.get('clock') or ''}"
        if state == "post":
            return "FT"
        return self.match.get("shortDetail") or "SCHEDULED"

    def _badge_class(self) -> str:
        state = self.match.get("state")
        if state == "in":
            return "live-badge"
        if state == "post":
            return "finished-badge"
        return "upcoming-badge"

    def _match_key(self) -> str:
        """Stable key used for diffing cards within a section."""
        return self.match.get("id", "")

    def compose(self) -> ComposeResult:
        home = next((t for t in self.match["teams"] if t["homeAway"] == "home"), {})
        away = next((t for t in self.match["teams"] if t["homeAway"] == "away"), {})
        state = self.match.get("state")
        show_scores = state in ("in", "post")
        home_goals = [g for g in self.match.get("goals", []) if g["teamId"] == home.get("id")] if show_scores else []
        away_goals = [g for g in self.match.get("goals", []) if g["teamId"] == away.get("id")] if show_scores else []
        venue = self.match.get("venue") or ""
        city = self.match.get("venueCity") or ""
        broadcasts = self.match.get("broadcasts", [])

        with Vertical(classes="match-card"):
            with Horizontal(classes="match-header"):
                with Horizontal(classes="header-left"):
                    yield Label(self._state_badge(), classes=f"badge {self._badge_class()}")
                    yield Label(_format_time(self.match.get("date", "")), classes="match-time")
                yield Label(self.match.get("group", ""), classes="match-group")

            with Horizontal(classes="scoreboard"):
                with Vertical(classes="team-col home-col"):
                    yield Label(home.get("name", "TBD"), classes="team-name")
                    yield Label(home.get("form", ""), classes="team-form")
                    if show_scores:
                        yield Label(str(home.get("score", "-")), classes="big-score")
                        yield Label(self._goals_text(home_goals, home.get("abbreviation", "")), classes="scorers")
                with Vertical(classes="center-col"):
                    yield Label("vs", classes="vs-badge")
                with Vertical(classes="team-col away-col"):
                    yield Label(away.get("name", "TBD"), classes="team-name")
                    yield Label(away.get("form", ""), classes="team-form")
                    if show_scores:
                        yield Label(str(away.get("score", "-")), classes="big-score")
                        yield Label(self._goals_text(away_goals, away.get("abbreviation", "")), classes="scorers")

            if show_scores:
                yield from self._render_stats(home, away)

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
    HeaderIcon {
        display: none;
    }
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
    #content {
        width: 100%;
        height: 1fr;
    }
    .section {
        width: 100%;
        height: 100%;
        display: none;
    }
    .section.active {
        display: block;
    }
    .section-title {
        width: 100%;
        height: auto;
        text-style: bold;
        color: $text;
        padding: 1 0 0 0;
    }
    #live-section .section-title {
        color: $error;
    }
    #upcoming-section .section-title {
        color: $warning;
    }
    #finished-section .section-title {
        color: $success;
    }
    #live-matches, #upcoming-matches, #finished-matches {
        width: 100%;
        height: 1fr;
    }
    #empty {
        width: 100%;
        height: 1fr;
        content-align: center middle;
        color: $text-muted;
        display: none;
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
    .badge {
        width: auto;
        text-style: bold;
    }
    .live-badge {
        color: $error;
    }
    .finished-badge {
        color: $success;
    }
    .upcoming-badge {
        color: $warning;
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
        ("right", "next_section", "Next section"),
        ("left", "prev_section", "Previous section"),
        ("up", "scroll_up", "Scroll up"),
        ("down", "scroll_down", "Scroll down"),
    ]

    SECTIONS = ["live-section", "upcoming-section", "finished-section"]

    matches = reactive(list)
    last_updated = reactive("")
    error_message = reactive("")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, icon="")
        with Vertical(id="main"):
            yield Label("Loading matches...", id="status")
            with VerticalScroll(id="content"):
                with Vertical(id="live-section", classes="section active"):
                    yield Label("🔴 Live Now", classes="section-title")
                    yield VerticalScroll(id="live-matches")
                with Vertical(id="upcoming-section", classes="section"):
                    yield Label("⏳ Upcoming", classes="section-title")
                    yield VerticalScroll(id="upcoming-matches")
                with Vertical(id="finished-section", classes="section"):
                    yield Label("✅ Finished", classes="section-title")
                    yield VerticalScroll(id="finished-matches")
            yield Label("", id="empty", classes="hidden")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "FIFA World Cup 2026 — Live"
        self.sub_title = "← →: section | ↑ ↓: scroll | R: refresh | Q: quit"
        self._next_match = None
        self._section_index = 0
        self.action_refresh()
        self.set_interval(REFRESH_SECONDS, self.action_refresh)
        self.set_interval(1, self._update_countdown)

    def action_prev_section(self) -> None:
        self._show_section(self._section_index - 1)

    def _active_scroll(self) -> VerticalScroll | None:
        section_id = self.SECTIONS[self._section_index]
        try:
            return self.query_one(f"#{section_id.replace('-section', '-matches')}", VerticalScroll)
        except Exception:
            return None

    def action_scroll_up(self) -> None:
        scroll = self._active_scroll()
        if scroll:
            scroll.scroll_up()

    def action_scroll_down(self) -> None:
        scroll = self._active_scroll()
        if scroll:
            scroll.scroll_down()

    def _show_section(self, index: int) -> None:
        self._section_index = index % len(self.SECTIONS)
        for i, section_id in enumerate(self.SECTIONS):
            section = self.query_one(f"#{section_id}", Vertical)
            if i == self._section_index:
                section.styles.display = "block"
                section.add_class("active")
            else:
                section.styles.display = "none"
                section.remove_class("active")
        self._sync_empty_banner()

    def action_next_section(self) -> None:
        self._show_section(self._section_index + 1)

    def _sync_empty_banner(self) -> None:
        empty = self.query_one("#empty", Label)
        content = self.query_one("#content", VerticalScroll)
        section_id = self.SECTIONS[self._section_index]
        section = self.query_one(f"#{section_id}", Vertical)
        has_matches = bool(section.query(MatchCard))
        if not has_matches:
            content.styles.display = "none"
            empty.styles.display = "block"
            if section_id == "live-section":
                empty.update(self._next_match_text())
            elif section_id == "upcoming-section":
                empty.update("No upcoming matches.\nPress R to refresh.")
            elif section_id == "finished-section":
                empty.update("No finished matches.\nPress R to refresh.")
        else:
            content.styles.display = "block"
            empty.styles.display = "none"

    def _update_section(self, section_id: str, matches: list) -> None:
        """Render match cards into a section, reusing existing cards when possible."""
        section = self.query_one(f"#{section_id}", Vertical)
        scroll = self.query_one(f"#{section_id.replace('-section', '-matches')}", VerticalScroll)

        if not matches:
            scroll.remove_children()
            section.styles.display = "none"
            return

        section.styles.display = "block"

        # Index existing cards by match id so we can update in place.
        existing: dict[str, MatchCard] = {}
        for child in scroll.query_children(MatchCard):
            key = child._match_key()
            if key:
                existing[key] = child

        seen: set[str] = set()
        to_mount: list[MatchCard] = []

        for match in matches:
            key = match.get("id", "")
            if key:
                seen.add(key)
            card = existing.get(key)
            if card is not None:
                # Same match: only rebuild if content changed.
                if card.match != match:
                    card.match = match
                    card.refresh(recompose=True)
            else:
                to_mount.append(MatchCard(match))

        # Remove cards no longer in the list.
        for key, card in list(existing.items()):
            if key not in seen:
                card.remove()

        # Mount new cards in batch.
        if to_mount:
            scroll.mount_all(to_mount)

    def watch_matches(self, matches: list) -> None:
        sorted_matches = _sort_matches(matches)
        live = [m for m in sorted_matches if m.get("state") == "in"]
        upcoming = [m for m in sorted_matches if m.get("state") == "pre"]
        finished = [m for m in sorted_matches if m.get("state") == "post"]

        self._update_section("live-section", live)
        self._update_section("upcoming-section", upcoming)
        self._update_section("finished-section", finished)

        # Surface the next upcoming match in the live section banner when nothing is live.
        if not live:
            self._next_match = _find_next_match(upcoming)
        else:
            self._next_match = None

        self._show_section(self._section_index)

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
        if not self._next_match or self.SECTIONS[self._section_index] != "live-section":
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
            live = [m for m in self.matches if m.get("state") == "in"]
            upcoming = [m for m in self.matches if m.get("state") == "pre"]
            finished = [m for m in self.matches if m.get("state") == "post"]
            self.last_updated = (
                f"Updated: {datetime.now().strftime('%H:%M:%S')} | "
                f"Live: {len(live)} | Upcoming: {len(upcoming)} | Finished: {len(finished)}"
            )
            self.error_message = ""
        except Exception as exc:
            self.error_message = str(exc)


if __name__ == "__main__":
    app = WorldCupTUI()
    app.run()
