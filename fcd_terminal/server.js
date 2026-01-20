const http = require("http");
const fs = require("fs");
const path = require("path");
const { URL } = require("url");

const PORT = process.env.PORT || 3000;
const rootDir = __dirname;
const geminiEndpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent";

const contentTypes = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "text/javascript",
  ".json": "application/json",
  ".png": "image/png",
  ".svg": "image/svg+xml"
};

const sendJson = (res, status, payload) => {
  const body = JSON.stringify(payload);
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(body);
};

const collectBody = (req) =>
  new Promise((resolve, reject) => {
    let data = "";
    req.on("data", (chunk) => {
      data += chunk;
    });
    req.on("end", () => {
      try {
        resolve(data ? JSON.parse(data) : {});
      } catch (error) {
        reject(error);
      }
    });
    req.on("error", reject);
  });

const buildGeminiRequest = (prompt, responseMimeType) => ({
  contents: [
    {
      role: "user",
      parts: [{ text: prompt }]
    }
  ],
  generationConfig: responseMimeType ? { responseMimeType } : undefined
});

const callGemini = async (prompt, responseMimeType) => {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    return { ok: false, status: 400, message: "Gemini API key missing. Set GEMINI_API_KEY to enable." };
  }

  try {
    const response = await fetch(`${geminiEndpoint}?key=${apiKey}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildGeminiRequest(prompt, responseMimeType))
    });

    if (!response.ok) {
      return { ok: false, status: response.status, message: "Gemini request failed." };
    }

    const data = await response.json();
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
    return { ok: true, text };
  } catch (error) {
    return { ok: false, status: 500, message: "Gemini request error." };
  }
};

const handleGeminiAnalysis = async (req, res) => {
  try {
    const body = await collectBody(req);
    const prompt = `You are a football valuation analyst. Provide a short analyst note with sections: Thesis, Bull case, Bear case, Key drivers, Confidence.\n\nSummary JSON:\n${JSON.stringify(body.summary, null, 2)}`;
    const result = await callGemini(prompt);

    if (!result.ok) {
      return sendJson(res, result.status, { message: result.message });
    }

    return sendJson(res, 200, { analysis: result.text || "Gemini returned no text." });
  } catch (error) {
    return sendJson(res, 400, { message: "Invalid JSON payload." });
  }
};

const handleGeminiScenario = async (req, res) => {
  try {
    const body = await collectBody(req);
    const prompt = `Given the current player state and scenario, return a JSON object with fields delta_value_eur_m, delta_confidence_points, ledger_entry_text, rationale.\n\nCurrent State:\n${JSON.stringify(body.current_state, null, 2)}\n\nScenario: ${body.scenario}`;
    const result = await callGemini(prompt, "application/json");

    if (!result.ok) {
      return sendJson(res, result.status, { message: result.message });
    }

    let impact;
    try {
      impact = JSON.parse(result.text);
    } catch (error) {
      impact = null;
    }

    if (!impact) {
      return sendJson(res, 422, { message: "Gemini did not return valid JSON." });
    }

    return sendJson(res, 200, { impact });
  } catch (error) {
    return sendJson(res, 400, { message: "Invalid JSON payload." });
  }
};

const serveStatic = (req, res) => {
  const requestUrl = new URL(req.url, `http://${req.headers.host}`);
  let pathname = requestUrl.pathname === "/" ? "/index.html" : requestUrl.pathname;
  const filePath = path.join(rootDir, pathname);

  if (!filePath.startsWith(rootDir)) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404, { "Content-Type": "text/plain" });
      res.end("Not Found");
      return;
    }
    const ext = path.extname(filePath);
    res.writeHead(200, { "Content-Type": contentTypes[ext] || "application/octet-stream" });
    res.end(data);
  });
};

const server = http.createServer((req, res) => {
  if (req.method === "POST" && req.url === "/api/gemini_analysis") {
    handleGeminiAnalysis(req, res);
    return;
  }

  if (req.method === "POST" && req.url === "/api/gemini_scenario") {
    handleGeminiScenario(req, res);
    return;
  }

  if (req.method === "GET") {
    serveStatic(req, res);
    return;
  }

  res.writeHead(405, { "Content-Type": "text/plain" });
  res.end("Method Not Allowed");
});

server.listen(PORT, () => {
  console.log(`FOOTBALL CLUB DATABASE running on http://localhost:${PORT}`);
});
