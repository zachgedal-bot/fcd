// ==== Quick-edit configuration ====
// Keep the app easy to tune by changing values here.
const CONFIG = {
  defaults: {
    anchorValue: 25,
    professionalismRisk: 40
  },
  projectionExpiries: [
    { label: "30d", days: 30 },
    { label: "90d", days: 90 },
    { label: "End of season", days: 210 }
  ],
  leagueMultipliers: {
    MLS: 0.85,
    "Premier League": 1.35,
    LaLiga: 1.25,
    Bundesliga: 1.2,
    SerieA: 1.15
  }
};

const state = {
  playerProfile: {
    player_id: "LAFC-99",
    name: "Denis Bouanga",
    age: 29,
    position: "LW",
    league: "MLS",
    current_wage_eur: 3500000,
    contract_end_date: "2025-12-31",
    option_year_probability: 0.65
  },
  anchorValue: CONFIG.defaults.anchorValue,
  professionalismRisk: CONFIG.defaults.professionalismRisk,
  analysisText: "",
  scenarioLedger: [],
  historyData: null,
  microEvents: null,
  charts: {}
};

const playerSchema = {
  type: "object",
  required: ["player_id", "player_name", "season", "league", "position", "matches"],
  properties: {
    player_id: { type: "string" },
    player_name: { type: "string" },
    season: { type: "string" },
    league: { type: "string" },
    position: { type: "string" },
    matches: {
      type: "array",
      items: {
        type: "object",
        required: ["date", "opponent", "minutes", "rating", "goals", "assists"],
        properties: {
          date: { type: "string" },
          opponent: { type: "string" },
          minutes: { type: "number" },
          rating: { type: "number" },
          goals: { type: "number" },
          assists: { type: "number" }
        }
      }
    }
  }
};

const microEventSchema = {
  type: "object",
  required: ["player_id", "events"],
  properties: {
    player_id: { type: "string" },
    events: {
      type: "array",
      items: {
        type: "object",
        required: ["date", "type", "impact", "notes"],
        properties: {
          date: { type: "string" },
          type: { type: "string" },
          impact: { type: "number" },
          notes: { type: "string" }
        }
      }
    }
  }
};

const playerProfileSchema = {
  type: "object",
  required: [
    "player_id",
    "name",
    "age",
    "position",
    "league",
    "current_wage_eur",
    "contract_end_date",
    "option_year_probability"
  ],
  properties: {
    player_id: { type: "string" },
    name: { type: "string" },
    age: { type: "number" },
    position: { type: "string" },
    league: { type: "string" },
    current_wage_eur: { type: "number" },
    contract_end_date: { type: "string" },
    option_year_probability: { type: "number" }
  }
};

const leagueMultipliers = CONFIG.leagueMultipliers;

const modeButtons = document.querySelectorAll(".mode-button");
const modePanels = document.querySelectorAll(".mode-panel");

const elements = {
  playerName: document.getElementById("player-name"),
  playerMeta: document.getElementById("player-meta"),
  indexPrice: document.getElementById("index-price"),
  confidenceScore: document.getElementById("confidence-score"),
  formSignal: document.getElementById("form-signal"),
  leagueMultiplier: document.getElementById("league-multiplier"),
  contractRunway: document.getElementById("contract-runway"),
  anchorValue: document.getElementById("anchor-value"),
  riskValue: document.getElementById("risk-value"),
  anchorSlider: document.getElementById("anchor-slider"),
  riskSlider: document.getElementById("risk-slider"),
  dealGauge: document.getElementById("deal-gauge"),
  dealLabel: document.getElementById("deal-label"),
  playerSummary: document.getElementById("player-summary"),
  projectionTable: document.getElementById("projection-table"),
  eventList: document.getElementById("event-list"),
  optionsList: document.getElementById("options-list"),
  analysisOutput: document.getElementById("analysis-output"),
  scenarioInput: document.getElementById("scenario-input"),
  scenarioSubmit: document.getElementById("scenario-submit"),
  scenarioLedger: document.getElementById("scenario-ledger"),
  refreshAnalysis: document.getElementById("refresh-analysis")
};

const formatCurrency = (value) => `€${value.toFixed(1)}m`;
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const getDaysBetween = (start, end) => {
  const startDate = new Date(start);
  const endDate = new Date(end);
  return Math.max(1, Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24)));
};

const validateSchema = (data, schema, path = "root") => {
  const errors = [];
  if (schema.type === "object") {
    if (typeof data !== "object" || data === null || Array.isArray(data)) {
      errors.push(`${path} should be an object`);
      return errors;
    }
    if (schema.required) {
      schema.required.forEach((key) => {
        if (!(key in data)) {
          errors.push(`${path}.${key} is required`);
        }
      });
    }
    if (schema.properties) {
      Object.entries(schema.properties).forEach(([key, childSchema]) => {
        if (data[key] !== undefined) {
          errors.push(...validateSchema(data[key], childSchema, `${path}.${key}`));
        }
      });
    }
  }

  if (schema.type === "array") {
    if (!Array.isArray(data)) {
      errors.push(`${path} should be an array`);
      return errors;
    }
    if (schema.items) {
      data.forEach((item, index) => {
        errors.push(...validateSchema(item, schema.items, `${path}[${index}]`));
      });
    }
  }

  if (schema.type === "string" && typeof data !== "string") {
    errors.push(`${path} should be a string`);
  }
  if (schema.type === "number" && typeof data !== "number") {
    errors.push(`${path} should be a number`);
  }
  return errors;
};

const computeMicroSignal = (events) => {
  if (!events || events.length === 0) {
    return 0;
  }
  const recent = events.slice(-5);
  const impactSum = recent.reduce((sum, event) => sum + event.impact, 0);
  return impactSum / recent.length;
};

// Core valuation model. Keep the math transparent and easy to tweak.
const computeValuation = () => {
  const { playerProfile, historyData, microEvents, anchorValue, professionalismRisk } = state;
  const matches = historyData.matches;
  const avgRating = matches.reduce((sum, match) => sum + match.rating, 0) / matches.length;
  const microSignal = computeMicroSignal(microEvents.events);
  const formSignal = (avgRating - 6) + microSignal * 4;
  const leagueMultiplier = leagueMultipliers[playerProfile.league] || 1;
  const ageFactor = playerProfile.age < 27 ? (27 - playerProfile.age) * 0.6 : (27 - playerProfile.age) * 0.4;
  const wageFactor = -(playerProfile.current_wage_eur / 1000000) * 0.35;
  const contractDays = getDaysBetween(new Date(), playerProfile.contract_end_date);
  const contractRunway = contractDays / 365;
  const contractFactor = Math.min(contractRunway, 2) * 1.4 + playerProfile.option_year_probability * 1.1;
  const baseValue = (anchorValue + formSignal * 2.2 + ageFactor + wageFactor + contractFactor) * leagueMultiplier;
  const timeDecay = 1 + (120 / Math.max(contractDays, 30));
  const indexPrice = Math.max(4, baseValue / timeDecay);
  const coverageRatio = Math.min(matches.length / 10, 1);
  const riskFactor = professionalismRisk / 100;
  const confidenceScore = clamp(55 + coverageRatio * 28 - (1 - riskFactor) * 12, 25, 100);
  const intervalWidth = 2 + (1 - coverageRatio) * 4 + (1 - riskFactor) * 3;

  return {
    indexPrice,
    confidenceScore,
    formSignal,
    leagueMultiplier,
    contractRunway,
    intervalWidth,
    microSignal
  };
};

const buildProjectionRows = (valuation) => {
  const { indexPrice, confidenceScore, intervalWidth } = valuation;
  const now = new Date();
  const expiries = [
    ...CONFIG.projectionExpiries,
    { label: "Contract end", days: getDaysBetween(now, state.playerProfile.contract_end_date) }
  ];

  return expiries.map((expiry) => {
    const decay = 1 + expiry.days / 365;
    const projected = Math.max(2, indexPrice / decay);
    const confidence = Math.max(18, confidenceScore - expiry.days / 20);
    return {
      label: expiry.label,
      projected: projected.toFixed(1),
      confidence: `${confidence.toFixed(0)}% ± ${intervalWidth.toFixed(1)}`,
      days: expiry.days
    };
  });
};

const renderOverview = (valuation) => {
  elements.playerName.textContent = state.playerProfile.name;
  elements.playerMeta.textContent = `${state.playerProfile.position} · ${state.playerProfile.league} · Age ${state.playerProfile.age}`;
  elements.indexPrice.textContent = formatCurrency(valuation.indexPrice);
  elements.confidenceScore.textContent = `Confidence ${valuation.confidenceScore.toFixed(0)} / 100`;
  elements.formSignal.textContent = valuation.formSignal.toFixed(2);
  elements.leagueMultiplier.textContent = valuation.leagueMultiplier.toFixed(2);
  elements.contractRunway.textContent = `${valuation.contractRunway.toFixed(2)} yrs`;
  elements.anchorValue.textContent = state.anchorValue;
  elements.riskValue.textContent = state.professionalismRisk;

  const summaryItems = [
    `Market anchor: €${state.anchorValue}m`,
    `Current wage: €${(state.playerProfile.current_wage_eur / 1000000).toFixed(2)}m / year`,
    `Contract end: ${state.playerProfile.contract_end_date}`,
    `Option year probability: ${(state.playerProfile.option_year_probability * 100).toFixed(0)}%`,
    `Rolling micro signal: ${valuation.microSignal.toFixed(2)}`
  ];

  elements.playerSummary.innerHTML = summaryItems
    .map((item) => `<li class="rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2">${item}</li>`)
    .join("");

  const projectionRows = buildProjectionRows(valuation);
  elements.projectionTable.innerHTML = projectionRows
    .map(
      (row) => `
        <tr>
          <td class="px-3 py-2">${row.label}</td>
          <td class="px-3 py-2">€${row.projected}</td>
          <td class="px-3 py-2">${row.confidence}</td>
        </tr>
      `
    )
    .join("");
};

const renderDealGauge = (valuation) => {
  const diff = valuation.indexPrice - state.anchorValue;
  const ratio = Math.max(0, Math.min(1, (valuation.indexPrice / Math.max(state.anchorValue, 1)) / 2));
  const width = Math.min(100, Math.max(10, ratio * 100));
  elements.dealGauge.style.width = `${width}%`;

  let label = "Fairly priced";
  if (diff > 3) label = "Overpriced";
  if (diff < -3) label = "Undervalued";
  elements.dealLabel.textContent = `${label} vs market anchor (${diff.toFixed(1)}m)`;
};

const renderHistory = () => {
  const matches = state.historyData.matches;
  const events = state.microEvents.events;

  elements.eventList.innerHTML = events
    .map(
      (event) => `
      <li class="rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2">
        <div class="flex items-center justify-between">
          <span class="text-emerald-300">${event.type.replace(/_/g, " ")}</span>
          <span class="text-xs text-slate-400">${event.date}</span>
        </div>
        <p class="mt-1 text-xs text-slate-300">${event.notes}</p>
      </li>
    `
    )
    .join("");

  const labels = matches.map((match) => match.date);
  const indexValues = matches.map((match) => {
    const ratingLift = (match.rating - 6) * 2.4;
    return Math.max(4, state.anchorValue + ratingLift);
  });

  const eventPoints = events.map((event) => {
    const matchIndex = labels.indexOf(event.date);
    return {
      x: matchIndex === -1 ? event.date : labels[matchIndex],
      y: indexValues[matchIndex] || state.anchorValue
    };
  });

  if (state.charts.history) {
    state.charts.history.data.labels = labels;
    state.charts.history.data.datasets[0].data = indexValues;
    state.charts.history.data.datasets[1].data = eventPoints;
    state.charts.history.update();
    return;
  }

  const ctx = document.getElementById("history-chart").getContext("2d");
  state.charts.history = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Index Price",
          data: indexValues,
          borderColor: "#22d3ee",
          backgroundColor: "rgba(34, 211, 238, 0.15)",
          tension: 0.35,
          fill: true
        },
        {
          label: "Events",
          data: eventPoints,
          type: "scatter",
          backgroundColor: "#facc15",
          borderColor: "#facc15",
          pointRadius: 5
        }
      ]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { color: "#cbd5f5" } }
      },
      scales: {
        x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(148, 163, 184, 0.1)" } },
        y: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(148, 163, 184, 0.1)" } }
      }
    }
  });
};

const renderOptions = (valuation) => {
  const projectionRows = buildProjectionRows(valuation);
  const labels = projectionRows.map((row) => row.label);
  const baseValues = projectionRows.map((row) => Number(row.projected));
  const upperBand = baseValues.map((value) => value + valuation.intervalWidth * 1.8);
  const lowerBand = baseValues.map((value) => Math.max(0, value - valuation.intervalWidth * 1.8));

  elements.optionsList.innerHTML = projectionRows
    .map(
      (row) => `
      <li class="rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2">
        <div class="flex items-center justify-between">
          <span>${row.label} projection</span>
          <span class="text-emerald-300">€${row.projected}m</span>
        </div>
        <p class="mt-1 text-xs text-slate-400">Confidence ${row.confidence}</p>
      </li>
    `
    )
    .join("");

  if (state.charts.options) {
    state.charts.options.data.labels = labels;
    state.charts.options.data.datasets[0].data = upperBand;
    state.charts.options.data.datasets[1].data = lowerBand;
    state.charts.options.data.datasets[2].data = baseValues;
    state.charts.options.update();
    return;
  }

  const ctx = document.getElementById("options-chart").getContext("2d");
  state.charts.options = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Upper",
          data: upperBand,
          borderColor: "rgba(16, 185, 129, 0)",
          backgroundColor: "rgba(34, 197, 94, 0.15)",
          fill: "+1"
        },
        {
          label: "Lower",
          data: lowerBand,
          borderColor: "rgba(14, 116, 144, 0)",
          backgroundColor: "rgba(14, 116, 144, 0.1)",
          fill: false
        },
        {
          label: "Projection",
          data: baseValues,
          borderColor: "#38bdf8",
          backgroundColor: "rgba(56, 189, 248, 0.2)",
          tension: 0.35
        }
      ]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { color: "#cbd5f5" } }
      },
      scales: {
        x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(148, 163, 184, 0.1)" } },
        y: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(148, 163, 184, 0.1)" } }
      }
    }
  });
};

const updateUI = () => {
  const valuation = computeValuation();
  renderOverview(valuation);
  renderDealGauge(valuation);
  renderHistory(valuation);
  renderOptions(valuation);
};

const handleModeSwitch = () => {
  modeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      modeButtons.forEach((btn) => btn.classList.remove("active"));
      button.classList.add("active");
      const mode = button.dataset.mode;
      modePanels.forEach((panel) => {
        panel.classList.toggle("hidden", panel.id !== `mode-${mode}`);
      });
    });
  });
};

const updateLedger = () => {
  if (state.scenarioLedger.length === 0) {
    elements.scenarioLedger.innerHTML = "";
    return;
  }
  elements.scenarioLedger.innerHTML = state.scenarioLedger
    .slice(-4)
    .map(
      (entry) => `
        <div class="rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2">
          <p class="text-emerald-300">${entry.ledger_entry_text}</p>
          <p class="mt-1 text-xs text-slate-400">${entry.rationale}</p>
        </div>
      `
    )
    .join("");
};

const showAnalysisMessage = (text, isError = false) => {
  elements.analysisOutput.textContent = text;
  elements.analysisOutput.classList.toggle("text-rose-300", isError);
};

const callGeminiAnalysis = async () => {
  const valuation = computeValuation();
  const summary = {
    player: state.playerProfile,
    valuation: {
      index_price_eur_m: valuation.indexPrice.toFixed(1),
      confidence_score: valuation.confidenceScore.toFixed(0),
      deal_label: elements.dealLabel.textContent
    },
    form_signal: valuation.formSignal.toFixed(2),
    contract_runway_years: valuation.contractRunway.toFixed(2),
    micro_signal: valuation.microSignal.toFixed(2)
  };

  showAnalysisMessage("Contacting Gemini for analyst note...");

  try {
    const response = await fetch("/api/gemini_analysis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ summary })
    });

    if (!response.ok) {
      const data = await response.json();
      showAnalysisMessage(data.message || "Gemini unavailable. Running offline.", true);
      return;
    }

    const data = await response.json();
    showAnalysisMessage(data.analysis || "Gemini returned an empty response.");
  } catch (error) {
    showAnalysisMessage("Gemini connection failed. Offline mode remains active.", true);
  }
};

const callGeminiScenario = async () => {
  const scenarioText = elements.scenarioInput.value.trim();
  if (!scenarioText) {
    showAnalysisMessage("Please enter a scenario prompt before submitting.", true);
    return;
  }
  const valuation = computeValuation();

  try {
    const response = await fetch("/api/gemini_scenario", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scenario: scenarioText,
        current_state: {
          player: state.playerProfile,
          index_price_eur_m: valuation.indexPrice,
          confidence_score: valuation.confidenceScore
        }
      })
    });

    if (!response.ok) {
      const data = await response.json();
      showAnalysisMessage(data.message || "Gemini scenario offline.", true);
      return;
    }

    const data = await response.json();
    const impact = data.impact || data;
    if (!impact || impact.delta_value_eur_m === undefined) {
      showAnalysisMessage("Gemini scenario response was invalid.", true);
      return;
    }

    state.anchorValue = Math.max(5, state.anchorValue + Number(impact.delta_value_eur_m));
    state.professionalismRisk = Math.min(
      100,
      Math.max(0, state.professionalismRisk + Number(impact.delta_confidence_points))
    );
    elements.anchorSlider.value = state.anchorValue;
    elements.riskSlider.value = state.professionalismRisk;
    state.scenarioLedger.push(impact);
    updateLedger();
    updateUI();
  } catch (error) {
    showAnalysisMessage("Gemini scenario failed. Offline mode remains active.", true);
  }
};

const init = async () => {
  handleModeSwitch();

  const profileErrors = validateSchema(state.playerProfile, playerProfileSchema);
  if (profileErrors.length) {
    showAnalysisMessage(`Profile schema errors: ${profileErrors.join(", ")}`, true);
  }

  const [historyResponse, microResponse] = await Promise.all([
    fetch("./data/bouanga_ratings_history.json"),
    fetch("./data/sample_player_micro_events.json")
  ]);

  state.historyData = await historyResponse.json();
  state.microEvents = await microResponse.json();

  const historyErrors = validateSchema(state.historyData, playerSchema);
  const microErrors = validateSchema(state.microEvents, microEventSchema);
  if (historyErrors.length || microErrors.length) {
    showAnalysisMessage(
      `Data schema errors: ${[...historyErrors, ...microErrors].join("; ")}`,
      true
    );
  }

  elements.anchorSlider.addEventListener("input", (event) => {
    state.anchorValue = Number(event.target.value);
    elements.anchorValue.textContent = state.anchorValue;
    updateUI();
  });

  elements.riskSlider.addEventListener("input", (event) => {
    state.professionalismRisk = Number(event.target.value);
    elements.riskValue.textContent = state.professionalismRisk;
    updateUI();
  });

  elements.refreshAnalysis.addEventListener("click", callGeminiAnalysis);
  elements.scenarioSubmit.addEventListener("click", callGeminiScenario);

  updateUI();
};

init();
