/**
 * FaceCode API helper
 * All calls to FastAPI backend (http://localhost:8000)
 */

const BASE = "http://localhost:8000";

async function req(path, method = "GET", body = null) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const API = {
  // Health
  health: () => req("/api/health"),

  // Emotion (REST fallback — WebSocket preferred for live stream)
  analyzeEmotion: (imageBase64, sessionId = "default") =>
    req("/api/analyze-emotion", "POST", { image_base64: imageBase64, session_id: sessionId }),

  // Problems
  getProblem: (sessionId = "default", difficulty = null) =>
    req("/api/get-problem", "POST", { session_id: sessionId, ...(difficulty && { difficulty }) }),

  listProblems: (difficulty = null) =>
    req(`/api/problems${difficulty ? `?difficulty=${difficulty}` : ""}`),

  // Code
  executeCode: (code, problemId, sessionId = "default") =>
    req("/api/execute-code", "POST", { code, problem_id: problemId, session_id: sessionId }),

  // Hints
  getHint: (sessionId = "default") =>
    req("/api/get-hint", "POST", { session_id: sessionId }),

  // Submit
  submitSolution: (problemId, code, sessionId = "default") =>
    req("/api/submit-solution", "POST", { problem_id: problemId, code, session_id: sessionId }),

  // Session stats
  getSessionStats: (sessionId = "default") =>
    req(`/api/session-stats?session_id=${sessionId}`),

  // Analytics (all-time)
  getAnalytics: () => req("/api/analytics"),
};
