const sourceRowsEl = document.getElementById("source-rows");
const liveRowsEl = document.getElementById("live-rows");
const sandboxStatusEl = document.getElementById("sandbox-status");
const loadSportsDbBtn = document.getElementById("load-sportsdb");
const loadStatsBombBtn = document.getElementById("load-statsbomb");
const ledgerBodyEl = document.getElementById("ledger-body");

const ledgerData = [
  { time: "09:14", event: "Coach request from UCLA", impact: "Awaiting response" },
  { time: "08:48", event: "Highlight reel updated", impact: "Tagged 3 coaches" },
  { time: "08:22", event: "GPA transcript verified", impact: "Academic badge awarded" },
  { time: "07:55", event: "New showcase invite", impact: "RSVP sent" },
  { time: "07:30", event: "Trainer recommendation added", impact: "Boosted profile rank" },
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
  updateSandboxStatus("Loading open player pool...");
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
    updateSandboxStatus("Loaded open player pool.");
  } catch (error) {
    updateSandboxStatus("Unable to load open player data.");
    liveRowsEl.innerHTML =
      '<tr><td colspan="4">Failed to load open player data.</td></tr>';
  }
}

async function loadStatsBombCompetitions() {
  updateSandboxStatus("Loading open competition list...");
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
    updateSandboxStatus("Loaded open competition list.");
  } catch (error) {
    updateSandboxStatus("Unable to load open competition data.");
    liveRowsEl.innerHTML =
      '<tr><td colspan="4">Failed to load open competition data.</td></tr>';
  }
}

function drawFallbackChart(canvas) {
  // Same series as the Chart.js config, drawn by hand so the panel never sits empty if the CDN is blocked.
  const labels = ["2019", "2020", "2021", "2022", "2023", "2024"];
  const series = [
    { data: [22, 40, 45, 60, 72, 88], color: "#38f0c7", fill: "rgba(56, 240, 199, 0.12)", dash: [] },
    { data: [null, 30, 38, 52, 63, 74], color: "rgba(62, 168, 255, 0.8)", fill: null, dash: [6, 6] },
  ];
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth || 600, hgt = canvas.clientHeight || 220;
  canvas.width = Math.round(w * dpr); canvas.height = Math.round(hgt * dpr);
  canvas.style.width = w + 'px'; canvas.style.height = hgt + 'px';
  const g = canvas.getContext("2d"); g.scale(dpr, dpr);
  const pad = { l: 42, r: 12, t: 12, b: 26 };
  const x = (i) => pad.l + (i / (labels.length - 1)) * (w - pad.l - pad.r);
  const y = (v) => pad.t + (1 - v / 100) * (hgt - pad.t - pad.b);
  g.strokeStyle = "rgba(30, 43, 59, 0.6)"; g.fillStyle = "#8b98aa"; g.font = "11px sans-serif"; g.textAlign = "right";
  for (let v = 0; v <= 100; v += 25) { g.beginPath(); g.moveTo(pad.l, y(v)); g.lineTo(w - pad.r, y(v)); g.stroke(); g.fillText(`${v}%`, pad.l - 6, y(v) + 4); }
  g.textAlign = "center"; labels.forEach((l, i) => g.fillText(l, x(i), hgt - 8));
  for (const s of series) {
    g.beginPath(); g.setLineDash(s.dash); g.strokeStyle = s.color; g.lineWidth = 2;
    let started = false;
    s.data.forEach((v, i) => { if (v == null) return; if (!started) { g.moveTo(x(i), y(v)); started = true; } else g.lineTo(x(i), y(v)); });
    g.stroke(); g.setLineDash([]);
    if (s.fill) { const first = s.data.findIndex((v) => v != null); g.lineTo(x(labels.length - 1), y(0)); g.lineTo(x(first), y(0)); g.closePath(); g.fillStyle = s.fill; g.fill(); }
  }
}

function initChart() {
  const ctx = document.getElementById("valuationChart");
  if (!ctx) return;
  if (typeof Chart === "undefined") { drawFallbackChart(ctx); window.addEventListener("resize", () => drawFallbackChart(ctx)); return; }

  new Chart(ctx, {
    type: "line",
    data: {
      labels: ["2019", "2020", "2021", "2022", "2023", "2024"],
      datasets: [
        {
          label: "Coach interest",
          data: [22, 40, 45, 60, 72, 88],
          borderColor: "#38f0c7",
          backgroundColor: "rgba(56, 240, 199, 0.12)",
          fill: true,
          tension: 0.35,
          pointRadius: 0,
        },
        {
          label: "Exposure index",
          data: [null, 30, 38, 52, 63, 74],
          borderColor: "rgba(62, 168, 255, 0.8)",
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
          grid: { color: "rgba(30, 43, 59, 0.6)" },
          ticks: { color: "#8b98aa" },
        },
        y: {
          grid: { color: "rgba(30, 43, 59, 0.6)" },
          ticks: {
            color: "#8b98aa",
            callback: (value) => `${value}%`,
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

// Coach requests: the counts are demo state, but the buttons act on it so nothing on the page is a dead end.
const requests = { pending: 12, held: 4 };
const toastEl = document.getElementById("toast");
let toastTimer = null;
function toast(message) {
  if (!toastEl) return;
  toastEl.textContent = message; toastEl.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { toastEl.hidden = true; }, 2600);
}
function renderRequests() {
  const approve = document.getElementById("req-approve"), hold = document.getElementById("req-hold");
  if (!approve || !hold) return;
  approve.textContent = requests.pending ? `Approve ${requests.pending}` : "All approved";
  hold.textContent = requests.held ? `Hold ${requests.held}` : "Nothing held";
  approve.disabled = !requests.pending; hold.disabled = !requests.held;
}
function logLedger(event, impact) {
  const now = new Date();
  ledgerData.unshift({ time: `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`, event, impact });
  ledgerData.length = Math.min(ledgerData.length, 8);
  renderLedger();
}
document.getElementById("req-approve")?.addEventListener("click", () => {
  if (!requests.pending) return;
  const n = requests.pending; requests.pending = 0;
  logLedger(`Approved ${n} coach requests`, "Coaches can now message");
  toast(`${n} coach requests approved.`); renderRequests();
});
document.getElementById("req-hold")?.addEventListener("click", () => {
  if (!requests.held) return;
  const n = requests.held; requests.held = 0;
  logLedger(`Released ${n} held requests for review`, "Moved to inbox");
  toast(`${n} held requests moved to your inbox.`); renderRequests();
});
renderRequests();

renderLedger();
initChart();
