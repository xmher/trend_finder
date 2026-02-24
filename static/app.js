/**
 * Trend Finder — Dashboard Frontend
 */

const state = {
    platform: null,
    category: null,
    minScore: 0,
    hours: 168,
    topKeywords: [],
    trends: [],
    discoveries: [],
    platforms: [],
    chart: null,
};

// ── API helpers ──

async function api(path) {
    const resp = await fetch(path);
    return resp.json();
}

// ── Data loading ──

async function loadPlatforms() {
    const data = await api("/api/platforms");
    state.platforms = data.platforms;
    renderPlatformBar();
}

async function loadTopKeywords() {
    const params = new URLSearchParams({ hours: state.hours, limit: 20 });
    const data = await api(`/api/trends/top?${params}`);
    state.topKeywords = data.trends;
    renderTopKeywords();
}

async function loadTrends() {
    const params = new URLSearchParams({
        hours: state.hours,
        min_score: state.minScore,
        limit: 100,
    });
    if (state.platform) params.set("platform", state.platform);
    if (state.category) params.set("category", state.category);

    const data = await api(`/api/trends?${params}`);
    state.trends = data.trends;
    renderTrendFeed();
}

async function loadTimeline(keyword) {
    const params = new URLSearchParams({ keyword, days: 7 });
    const data = await api(`/api/trends/timeline?${params}`);
    renderChart(data);
}

async function triggerFetch() {
    const btn = document.getElementById("fetch-btn");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Fetching...';

    await fetch("/api/fetch", { method: "POST" });

    // Poll for completion (give collectors time to run)
    let polls = 0;
    const pollInterval = setInterval(async () => {
        polls++;
        await refreshAll();
        if (polls >= 6) {
            clearInterval(pollInterval);
            btn.disabled = false;
            btn.textContent = "Fetch Now";
        }
    }, 5000);
}

async function loadDiscoveries() {
    const filter = document.getElementById("discovery-filter");
    const status = filter ? filter.value : "";
    const params = new URLSearchParams({ min_confidence: 0, limit: 50 });
    if (status) params.set("status", status);
    const data = await api(`/api/discoveries?${params}`);
    state.discoveries = data.discoveries;
    renderDiscoveries();
}

async function refreshAll() {
    await Promise.all([loadPlatforms(), loadTopKeywords(), loadTrends(), loadDiscoveries()]);
    const el = document.getElementById("last-updated");
    if (el) el.textContent = `Updated ${new Date().toLocaleTimeString()}`;
}

// ── Rendering ──

function renderPlatformBar() {
    const container = document.getElementById("platform-bar");
    const allChip = `<div class="platform-chip ${!state.platform ? 'active' : ''}"
                          onclick="filterPlatform(null)">
        <span>All Platforms</span>
    </div>`;

    const chips = state.platforms.map(p => `
        <div class="platform-chip ${state.platform === p.name ? 'active' : ''}"
             onclick="filterPlatform('${p.name}')">
            <span class="dot ${p.configured ? 'connected' : 'disconnected'}"></span>
            <span>${platformLabel(p.name)}</span>
            ${p.trends_found ? `<span style="color:var(--text-dim);font-size:11px">(${p.trends_found})</span>` : ''}
        </div>
    `).join("");

    container.innerHTML = allChip + chips;
}

function renderTopKeywords() {
    const container = document.getElementById("top-keywords");

    if (state.topKeywords.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h3>No trends yet</h3>
                <p>Click "Fetch Now" to pull trends from your configured platforms,
                   or add API keys in your .env file.</p>
            </div>`;
        return;
    }

    const items = state.topKeywords.map((t, i) => {
        const barWidth = Math.max(4, (t.max_relevance / 100) * 120);
        const platforms = t.platforms.map(p =>
            `<span class="badge badge-${p}">${platformLabel(p)}</span>`
        ).join(" ");

        return `
            <li class="keyword-item" onclick="selectKeyword('${escHtml(t.keyword)}')">
                <div>
                    <span class="kw-name">${i + 1}. ${escHtml(t.keyword)}</span>
                    <div style="margin-top:4px">${platforms}</div>
                </div>
                <div class="kw-meta">
                    <span>${formatNum(t.total_engagement)} eng.</span>
                    <span>${t.post_count} posts</span>
                    <span class="kw-score">${t.max_relevance}</span>
                    <span class="score-bar" style="width:${barWidth}px"></span>
                </div>
            </li>`;
    }).join("");

    container.innerHTML = `<ul class="keyword-list">${items}</ul>`;
}

function renderTrendFeed() {
    const container = document.getElementById("trend-feed");
    const countEl = document.getElementById("trend-count");
    if (countEl) countEl.textContent = `${state.trends.length} results`;

    if (state.trends.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h3>No matching trends</h3>
                <p>Try adjusting your filters or fetching new data.</p>
            </div>`;
        return;
    }

    const items = state.trends.map(t => {
        const title = t.title || t.keyword;
        const link = t.url
            ? `<a href="${escHtml(t.url)}" target="_blank" rel="noopener">${escHtml(title)}</a>`
            : escHtml(title);

        return `
            <li class="trend-entry">
                <div class="te-header">
                    <span class="te-title">${link}</span>
                    <span class="badge badge-${t.platform}">${platformLabel(t.platform)}</span>
                </div>
                <div class="te-meta">
                    <span>Score: ${t.relevance_score}</span>
                    <span>${formatNum(t.engagement)} engagement</span>
                    <span>${t.category}</span>
                    <span>${timeAgo(t.fetched_at)}</span>
                </div>
            </li>`;
    }).join("");

    container.innerHTML = `<ul class="trend-feed">${items}</ul>`;
}

function renderChart(data) {
    const ctx = document.getElementById("timeline-chart");
    if (!ctx) return;

    const title = document.getElementById("chart-title");
    if (title) title.textContent = `Trend: ${data.keyword}`;

    if (state.chart) state.chart.destroy();

    if (data.timeline.length === 0) {
        ctx.parentElement.innerHTML = `<div class="chart-container"><canvas id="timeline-chart"></canvas></div>
            <p style="color:var(--text-dim);text-align:center;padding:20px">
            No timeline data for this keyword yet. Check back after a few fetch cycles.</p>`;
        return;
    }

    const labels = data.timeline.map(d => new Date(d.date).toLocaleDateString());
    const engagement = data.timeline.map(d => d.engagement);
    const scores = data.timeline.map(d => d.score);

    state.chart = new Chart(ctx, {
        type: "line",
        data: {
            labels,
            datasets: [
                {
                    label: "Engagement",
                    data: engagement,
                    borderColor: "#a855f7",
                    backgroundColor: "rgba(168,85,247,0.1)",
                    fill: true,
                    tension: 0.3,
                    yAxisID: "y",
                },
                {
                    label: "Relevance Score",
                    data: scores,
                    borderColor: "#34d399",
                    borderDash: [4, 4],
                    tension: 0.3,
                    yAxisID: "y1",
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { labels: { color: "#8888a0" } },
            },
            scales: {
                x: { ticks: { color: "#8888a0" }, grid: { color: "#2a2a3a" } },
                y: {
                    type: "linear", position: "left",
                    ticks: { color: "#a855f7" }, grid: { color: "#2a2a3a" },
                    title: { display: true, text: "Engagement", color: "#a855f7" },
                },
                y1: {
                    type: "linear", position: "right",
                    ticks: { color: "#34d399" }, grid: { display: false },
                    title: { display: true, text: "Score", color: "#34d399" },
                    min: 0, max: 100,
                },
            },
        },
    });
}

function renderDiscoveries() {
    const container = document.getElementById("discovery-feed");
    const countEl = document.getElementById("discovery-count");
    if (!container) return;

    if (countEl) countEl.textContent = `${state.discoveries.length} found`;

    if (state.discoveries.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h3>No discoveries yet</h3>
                <p>After a fetch cycle, the discovery pipeline will surface trending keywords you didn't know about.</p>
            </div>`;
        return;
    }

    const items = state.discoveries.map(d => {
        const confColor = d.confidence >= 60 ? "var(--green)" : d.confidence >= 35 ? "var(--orange)" : "var(--text-dim)";
        const confBar = Math.max(4, (d.confidence / 100) * 100);
        const platforms = d.platforms_seen.map(p =>
            `<span class="badge badge-${p}">${platformLabel(p)}</span>`
        ).join(" ");

        const statusBadge = d.status === "promoted"
            ? `<span class="disc-status promoted">promoted</span>`
            : d.status === "dismissed"
            ? `<span class="disc-status dismissed">dismissed</span>`
            : "";

        const actions = d.status === "new" ? `
            <div class="disc-actions">
                <button class="btn-sm btn-promote" onclick="promoteDiscovery(${d.id})">Promote</button>
                <button class="btn-sm btn-dismiss" onclick="dismissDiscovery(${d.id})">Dismiss</button>
            </div>` : "";

        return `
            <li class="disc-entry">
                <div class="disc-header">
                    <div>
                        <span class="disc-keyword">${escHtml(d.keyword)}</span>
                        ${statusBadge}
                    </div>
                    <div class="disc-confidence" style="color:${confColor}">
                        ${d.confidence.toFixed(0)}%
                        <span class="conf-bar" style="width:${confBar}px;background:${confColor}"></span>
                    </div>
                </div>
                <div class="disc-context">${escHtml(d.source_context)}</div>
                <div class="disc-meta">
                    ${platforms}
                    <span>seen ${d.times_seen}x</span>
                    ${d.peak_engagement > 0 ? `<span>${formatNum(d.peak_engagement)} peak eng.</span>` : ""}
                    <span>first ${timeAgo(d.first_seen_at)}</span>
                </div>
                ${actions}
            </li>`;
    }).join("");

    container.innerHTML = `<ul class="disc-list">${items}</ul>`;
}

async function promoteDiscovery(id) {
    await fetch(`/api/discoveries/${id}/promote`, { method: "POST" });
    loadDiscoveries();
}

async function dismissDiscovery(id) {
    await fetch(`/api/discoveries/${id}/dismiss`, { method: "POST" });
    loadDiscoveries();
}

// ── User actions ──

function filterPlatform(platform) {
    state.platform = platform;
    // Sync dropdown
    const sel = document.getElementById("filter-platform");
    if (sel) sel.value = platform || "";
    loadTrends();
    renderPlatformBar();
}

function selectKeyword(keyword) {
    loadTimeline(keyword);
}

function onFilterChange() {
    const platform = document.getElementById("filter-platform").value;
    const category = document.getElementById("filter-category").value;
    const minScore = parseInt(document.getElementById("filter-score").value, 10);
    const hours = parseInt(document.getElementById("filter-hours").value, 10);

    state.platform = platform || null;
    state.category = category || null;
    state.minScore = minScore;
    state.hours = hours;

    renderPlatformBar();
    loadTopKeywords();
    loadTrends();
}

// ── Utilities ──

const PLATFORM_LABELS = {
    reddit: "Reddit",
    twitter: "Twitter/X",
    tiktok: "TikTok",
    pinterest: "Pinterest",
    threads: "Threads",
    google_trends: "Google Trends",
};

function platformLabel(name) {
    return PLATFORM_LABELS[name] || capitalize(name);
}

function capitalize(s) {
    return s.charAt(0).toUpperCase() + s.slice(1);
}

function formatNum(n) {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
    return String(n);
}

function timeAgo(isoDate) {
    if (!isoDate) return "";
    const diff = Date.now() - new Date(isoDate).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
}

function escHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
}

// ── Init ──

document.addEventListener("DOMContentLoaded", () => {
    refreshAll();

    // Auto-refresh every 5 minutes
    setInterval(refreshAll, 5 * 60 * 1000);
});
