const sourceRowsEl = document.getElementById("source-rows");
const liveRowsEl = document.getElementById("live-rows");
const sandboxStatusEl = document.getElementById("sandbox-status");
const loadSportsDbBtn = document.getElementById("load-sportsdb");
const loadStatsBombBtn = document.getElementById("load-statsbomb");
const ledgerBodyEl = document.getElementById("ledger-body");

const ledgerData = [
  { time: "14:32", event: "Goal vs ARS", impact: "+€0.85M" },
  { time: "14:05", event: "Shot on Target (0.4 xG)", impact: "+€0.12M" },
  { time: "13:45", event: "Half Time Adjustment", impact: "-€0.05M" },
  { time: "13:22", event: "Dispossessed (Def. 3rd)", impact: "-€0.15M" },
  { time: "13:10", event: "Progressive Pass (+0.04 g+)", impact: "+€0.02M" },
];

function renderLedger() {
  ledgerBodyEl.innerHTML = ledgerData
    .map(
      (row) => `
        <tr>
          <td>${row.time}</td>
          <td>${row.event}</td>
          <td>${row.impact}</td>
        </tr>
      `
    )
    .join("");
}

function renderSources(list) {
  const freeSources = list.filter((source) =>
    ["public", "unofficial"].includes(source.api_status)
  );
  const displayList = (freeSources.length ? freeSources : list).slice(0, 8);

  sourceRowsEl.innerHTML = displayList
    .map((source) => {
      const badgeClass = `badge badge--${source.api_status}`;
      return `
        <li class="feed">
          <span>${source.name}</span>
          <span class="${badgeClass}">${source.api_status.replace(/_/g, " ")}</span>
        </li>
      `;
    })
    .join("");
}

function renderLiveRows(list) {
  liveRowsEl.innerHTML = list
    .map(
      (row) => `
        <tr>
          <td>${row.source}</td>
          <td>${row.name}</td>
          <td>${row.team}</td>
          <td>${row.detail}</td>
        </tr>
      `
    )
    .join("");
}

function updateSandboxStatus(message) {
  sandboxStatusEl.textContent = message;
}

async function loadSportsDbPlayers() {
  updateSandboxStatus("Loading TheSportsDB players...");
  try {
    const response = await fetch(
      "https://www.thesportsdb.com/api/v1/json/1/searchplayers.php?t=Arsenal"
    );
    if (!response.ok) {
      throw new Error("TheSportsDB request failed");
    }
    const data = await response.json();
    const players = Array.isArray(data.player) ? data.player : [];
    const rows = players.slice(0, 10).map((player) => ({
      source: "TheSportsDB",
      name: player.strPlayer || "Unknown",
      team: player.strTeam || "Unknown",
      detail: player.strNationality || "Unknown nationality",
    }));
    renderLiveRows(rows);
    updateSandboxStatus("Loaded TheSportsDB player list.");
  } catch (error) {
    updateSandboxStatus("Unable to load TheSportsDB data.");
    liveRowsEl.innerHTML =
      '<tr><td colspan="4">Failed to load TheSportsDB data.</td></tr>';
  }
}

async function loadStatsBombCompetitions() {
  updateSandboxStatus("Loading StatsBomb open data...");
  try {
    const response = await fetch(
      "https://raw.githubusercontent.com/statsbomb/open-data/master/data/competitions.json"
    );
    if (!response.ok) {
      throw new Error("StatsBomb request failed");
    }
    const data = await response.json();
    const competitions = Array.isArray(data) ? data : [];
    const rows = competitions.slice(0, 10).map((competition) => ({
      source: "StatsBomb Open Data",
      name: competition.competition_name || "Unknown competition",
      team: competition.country_name || "Unknown country",
      detail: `Season: ${competition.season_name || "Unknown"}`,
    }));
    renderLiveRows(rows);
    updateSandboxStatus("Loaded StatsBomb open data.");
  } catch (error) {
    updateSandboxStatus("Unable to load StatsBomb open data.");
    liveRowsEl.innerHTML =
      '<tr><td colspan="4">Failed to load StatsBomb open data.</td></tr>';
  }
}

function initChart() {
  const ctx = document.getElementById("valuationChart");
  if (!ctx) return;

  new Chart(ctx, {
    type: "line",
    data: {
      labels: ["2020", "2021", "2022", "2023", "2024", "2025", "2026"],
      datasets: [
        {
          label: "Market Value",
          data: [64, 85, 75, 50, 48, 45, 42],
          borderColor: "#7bdcff",
          backgroundColor: "rgba(123, 220, 255, 0.08)",
          fill: true,
          tension: 0.35,
          pointRadius: 0,
        },
        {
          label: "Projection",
          data: [null, null, null, 50, 48, 42, 30],
          borderColor: "rgba(248, 113, 113, 0.8)",
          borderDash: [6, 6],
          tension: 0.35,
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          grid: { color: "rgba(30, 38, 54, 0.6)" },
          ticks: { color: "#8b98aa" },
        },
        y: {
          grid: { color: "rgba(30, 38, 54, 0.6)" },
          ticks: {
            color: "#8b98aa",
            callback: (value) => `€${value}m`,
          },
        },
      },
    },
  });
}

fetch("sources.json")
  .then((response) => {
    if (!response.ok) {
      throw new Error("Failed to load sources");
    }
    return response.json();
  })
  .then((data) => {
    renderSources(Array.isArray(data) ? data : []);
  })
  .catch(() => {
    sourceRowsEl.innerHTML = "<li>Unable to load data feeds.</li>";
  });

loadSportsDbBtn.addEventListener("click", loadSportsDbPlayers);
loadStatsBombBtn.addEventListener("click", loadStatsBombCompetitions);

renderLedger();
initChart();
