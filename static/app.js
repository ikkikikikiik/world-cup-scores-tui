const API_URL = "/api/scoreboard";
const matchesEl = document.getElementById("matches");
const liveSectionEl = document.getElementById("live-section");
const liveMatchesEl = document.getElementById("live-matches");
const lastUpdatedEl = document.getElementById("last-updated");
const refreshBtn = document.getElementById("refresh-btn");

let pollInterval = null;

function formatTime(isoString) {
    if (!isoString) return "";
    const date = new Date(isoString);
    return date.toLocaleString(undefined, {
        weekday: "short",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function getStateClass(state) {
    if (state === "in") return "live";
    if (state === "post") return "finished";
    return "upcoming";
}

function getStateBadge(state, detail) {
    if (state === "in") return `<span class="badge live-badge">● LIVE ${detail || ""}</span>`;
    if (state === "post") return `<span class="badge finished-badge">FT</span>`;
    return `<span class="badge upcoming-badge">${detail || "Scheduled"}</span>`;
}

function renderTeam(team, isHome) {
    const logo = team.logo ? `<img src="${team.logo}" alt="${team.name}" class="team-logo">` : "";
    return `
        <div class="team ${isHome ? "home" : "away"}">
            <div class="team-main">
                <div class="team-info">
                    ${logo}
                    <div>
                        <div class="team-name">${team.name}</div>
                        <div class="team-form" title="Recent form">${team.form || ""}</div>
                    </div>
                </div>
                <div class="score">${team.score !== undefined ? team.score : "-"}</div>
            </div>
        </div>
    `;
}

function renderTeamWithGoals(team, isHome, goals) {
    const logo = team.logo ? `<img src="${team.logo}" alt="${team.name}" class="team-logo">` : "";
    const teamGoals = goals ? goals.filter((g) => g.teamId === team.id) : [];
    const abbr = team.abbreviation || "";
    const goalsHtml = teamGoals.length
        ? teamGoals.map((g) => {
            const icon = g.penalty ? "⚽ (P)" : g.ownGoal ? "⚽ (OG)" : "⚽";
            return `<div class="goal">${icon} <strong>${g.scorer || "?"}</strong> <span class="goal-team">(${abbr})</span> ${g.minute}</div>`;
        }).join("")
        : "";
    return `
        <div class="team ${isHome ? "home" : "away"}">
            <div class="team-main">
                <div class="team-info">
                    ${logo}
                    <div>
                        <div class="team-name">${team.name}</div>
                        <div class="team-form" title="Recent form">${team.form || ""}</div>
                    </div>
                </div>
                <div class="score">${team.score !== undefined ? team.score : "-"}</div>
            </div>
            ${goalsHtml ? `<div class="team-goals">${goalsHtml}</div>` : ""}
        </div>
    `;
}

function renderGoals(goals, teams) {
    if (!goals || goals.length === 0) return "";
    const teamMap = new Map(teams.map((t) => [t.id, t.abbreviation]));
    const items = goals.map((g) => {
        const icon = g.penalty ? "⚽ (P)" : g.ownGoal ? "⚽ (OG)" : "⚽";
        const abbr = teamMap.get(g.teamId) || "";
        return `<div class="goal">${icon} <strong>${g.scorer || "?"}</strong> <span class="goal-team">(${abbr})</span> ${g.minute}</div>`;
    });
    return `<div class="goals">${items.join("")}</div>`;
}

function renderStats(teams) {
    if (!teams || teams.length < 2) return "";
    const stats = [
        { label: "Possession", key: "possession", suffix: "%" },
        { label: "Shots", key: "shots" },
        { label: "On Target", key: "shotsOnTarget" },
        { label: "Corners", key: "corners" },
        { label: "Fouls", key: "fouls" },
    ];
    const home = teams[0].stats || {};
    const away = teams[1].stats || {};
    const rows = stats
        .map((s) => {
            const h = home[s.key];
            const a = away[s.key];
            if (h == null && a == null) return "";
            return `
                <div class="stat-row">
                    <span>${h ?? "-"}${s.suffix || ""}</span>
                    <span class="stat-label">${s.label}</span>
                    <span>${a ?? "-"}${s.suffix || ""}</span>
                </div>
            `;
        })
        .join("");
    return rows ? `<div class="stats">${rows}</div>` : "";
}

function renderMatch(match) {
    const home = match.teams.find((t) => t.homeAway === "home");
    const away = match.teams.find((t) => t.homeAway === "away");
    const stateClass = getStateClass(match.state);
    const broadcast = match.broadcasts?.length ? `📺 ${match.broadcasts.join(", ")}` : "";
    const venue = match.venue ? `🏟️ ${match.venue}${match.venueCity ? `, ${match.venueCity}` : ""}` : "";

    const isLive = match.state === "in";
    const teamsHtml = isLive
        ? `${renderTeamWithGoals(home, true, match.goals)}${renderTeamWithGoals(away, false, match.goals)}`
        : `${renderTeam(home, true)}${renderTeam(away, false)}`;

    return `
        <article class="match-card ${stateClass}" data-id="${match.id}" data-state="${match.state}">
            <div class="match-header">
                <div class="match-meta">
                    ${getStateBadge(match.state, match.clock || match.shortDetail)}
                    <span class="match-time">${formatTime(match.date)}</span>
                </div>
                <div class="match-group">${match.group || ""}</div>
            </div>
            <div class="match-body">
                ${teamsHtml}
            </div>
            ${isLive ? "" : renderGoals(match.goals, match.teams)}
            ${renderStats(match.teams)}
            <div class="match-footer">
                <span>${venue}</span>
                <span>${broadcast}</span>
            </div>
        </article>
    `;
}

function sortMatches(matches) {
    const stateOrder = { in: 0, post: 1, pre: 2 };
    return [...matches].sort((a, b) => {
        const stateDiff = (stateOrder[a.state] ?? 3) - (stateOrder[b.state] ?? 3);
        if (stateDiff !== 0) return stateDiff;

        const aDate = new Date(a.date).getTime();
        const bDate = new Date(b.date).getTime();

        // Within live: earliest kickoff first
        // Within finished: most recently completed first (descending date)
        // Within upcoming: next to play first (ascending date)
        if (a.state === "post") return bDate - aDate;
        return aDate - bDate;
    });
}

function updateContainer(container, matches, renderFn) {
    const existingCards = new Map(
        Array.from(container.children)
            .filter((c) => c.classList.contains("match-card"))
            .map((c) => [c.dataset.id, c])
    );

    const seen = new Set();
    const fragment = document.createDocumentFragment();

    matches.forEach((match) => {
        seen.add(String(match.id));
        const html = renderFn(match);
        const existingCard = existingCards.get(String(match.id));

        if (!existingCard) {
            const wrapper = document.createElement("div");
            wrapper.innerHTML = html.trim();
            fragment.appendChild(wrapper.firstElementChild);
            return;
        }

        // Only replace the card if its content actually changed.
        if (existingCard.outerHTML !== html.trim()) {
            const wrapper = document.createElement("div");
            wrapper.innerHTML = html.trim();
            container.replaceChild(wrapper.firstElementChild, existingCard);
        }
    });

    // Remove cards that are no longer present.
    existingCards.forEach((card, id) => {
        if (!seen.has(id)) card.remove();
    });

    // Clear loading/empty/error placeholders once real cards are rendered.
    if (matches.length > 0) {
        Array.from(container.children)
            .filter((c) => !c.classList.contains("match-card"))
            .forEach((c) => c.remove());
    }

    if (fragment.childNodes.length > 0) {
        container.appendChild(fragment);
    }
}

function render(data) {
    lastUpdatedEl.textContent = `Updated: ${new Date(data.fetchedAt).toLocaleTimeString()}`;

    const allMatches = sortMatches(data.matches || []);
    const liveMatches = allMatches.filter((m) => m.state === "in");
    const gridMatches = allMatches.filter((m) => m.state !== "in");

    if (liveMatches.length > 0) {
        liveSectionEl.classList.remove("hidden");
        updateContainer(liveMatchesEl, liveMatches, renderMatch);
    } else {
        liveSectionEl.classList.add("hidden");
        liveMatchesEl.innerHTML = "";
    }

    if (gridMatches.length === 0) {
        matchesEl.innerHTML = `<div class="empty">No matches found.</div>`;
        return;
    }

    updateContainer(matchesEl, gridMatches, renderMatch);
}

async function loadData() {
    try {
        const resp = await fetch(API_URL);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        render(data);
    } catch (err) {
        matchesEl.innerHTML = `<div class="error">Failed to load matches: ${err.message}</div>`;
    }
}

function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    loadData();
    pollInterval = setInterval(loadData, 15000);
}

refreshBtn.addEventListener("click", async () => {
    lastUpdatedEl.textContent = "Refreshing...";
    await loadData();
});

startPolling();
