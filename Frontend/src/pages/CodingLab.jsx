import { useState, useEffect, useRef } from "react";
import { API } from "../api";

// Use relative URL so it goes through Vite's proxy (port 3000 → 8000)
// This avoids Windows IPv4/IPv6 mismatch on localhost and bypasses CORS on WebSocket
const WS_URL = `ws://${window.location.host}/ws/emotion-stream`;
const WS_MAX_RETRIES = 5;
const WS_RETRY_DELAY_MS = 2000; // 2s between retries
const FRAME_INTERVAL_MS = 1500;

const EMOTION_EMOJI = {
  happy: "😊", neutral: "😐", sad: "😢",
  angry: "😠", surprise: "😮", fear: "😨",
  disgust: "🤢", confused: "😕",
};

// ── CodeEditor (textarea with line numbers) ────────────────────────────────
function CodeEditor({ value, onChange }) {
  const lines = value.split("\n").length;
  return (
    <div className="code-editor-wrap">
      <div className="line-numbers">
        {Array.from({ length: Math.max(lines, 15) }, (_, i) => (
          <span key={i}>{i + 1}</span>
        ))}
      </div>
      <textarea
        className="code-textarea"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        spellCheck={false}
        autoComplete="off"
        autoCorrect="off"
      />
    </div>
  );
}

// ── Confidence Ring ────────────────────────────────────────────────────────
function ConfidenceRing({ value }) {
  const r = 44;
  const circ = 2 * Math.PI * r;
  const dash = circ * value;
  const color = value >= 0.7 ? "#00e5a0" : value >= 0.4 ? "#f5c542" : "#ff5c5c";

  return (
    <div className="conf-ring-wrap">
      <svg width="110" height="110" viewBox="0 0 110 110">
        <circle cx="55" cy="55" r={r} fill="none" stroke="#1a1f2e" strokeWidth="10" />
        <circle
          cx="55" cy="55" r={r} fill="none"
          stroke={color} strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circ}`}
          strokeDashoffset={circ * 0.25}
          style={{ transition: "stroke-dasharray 0.6s ease, stroke 0.4s ease" }}
        />
      </svg>
      <div className="conf-ring-label">
        <span className="conf-pct" style={{ color }}>{Math.round(value * 100)}%</span>
        <span className="conf-text">confidence</span>
      </div>
    </div>
  );
}

// ── Test Results Panel ─────────────────────────────────────────────────────
function TestResults({ results }) {
  if (!results) return null;
  const passed = results.test_results?.filter((t) => t.passed).length ?? 0;
  const total = results.test_results?.length ?? 0;
  return (
    <div className={`test-panel ${results.all_passed ? "all-pass" : "some-fail"}`}>
      <div className="test-summary">
        <span>{results.all_passed ? "✅" : "⚠️"}</span>
        <strong>{passed}/{total} tests passed</strong>
        <span className="exec-time">{results.execution_time?.toFixed(2)}s</span>
      </div>
      {results.error && <div className="test-error">{results.error}</div>}
      <div className="test-cases">
        {results.test_results?.map((t, i) => (
          <div key={i} className={`test-case ${t.passed ? "pass" : "fail"}`}>
            <span>{t.passed ? "✓" : "✗"}</span>
            <span className="tc-label">Test {i + 1}</span>
            <span className="tc-input">in: {JSON.stringify(t.input)}</span>
            <span className="tc-expect">expected: {JSON.stringify(t.expected)}</span>
            {!t.passed && t.actual !== undefined && (
              <span className="tc-actual">got: {JSON.stringify(t.actual)}</span>
            )}
            {t.error && <span className="tc-err">{t.error}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main CodingLab ─────────────────────────────────────────────────────────
export default function CodingLab({ sessionId, onGoAnalytics }) {
  const [problem, setProblem] = useState(null);
  const [code, setCode] = useState("");
  const [running, setRunning] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [testResults, setTestResults] = useState(null);
  const [hints, setHints] = useState([]);
  const [hintLoading, setHintLoading] = useState(false);
  const [difficulty, setDifficulty] = useState("EASY");
  const [solved, setSolved] = useState(false);
  const [solveMsg, setSolveMsg] = useState(null);

  // Emotion state
  const [emotion, setEmotion] = useState("neutral");
  const [confidence, setConfidence] = useState(0.5);
  const [faceDetected, setFaceDetected] = useState(false);
  const [camError, setCamError] = useState(null);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const captureRef = useRef(null);
  const wsRef = useRef(null);

  // ── Load first problem ────────────────────────────────────────────────────
  useEffect(() => {
    isMounted.current = true;
    loadProblem();
    startWebcam();
    return () => stopWebcam();
  }, []);

  async function loadProblem(diff = null) {
    setSolved(false);
    setSolveMsg(null);
    setTestResults(null);
    setHints([]);
    try {
      const data = await API.getProblem(sessionId, diff);
      setProblem(data);
      setCode(data.starter_code || "");
      setDifficulty(data.difficulty);
    } catch (e) {
      console.error("Failed to load problem:", e);
    }
  }

  // ── Webcam + WebSocket emotion stream ────────────────────────────────────
  // retryCount lives outside React state so it doesn't cause re-renders
  const retryCount = useRef(0);
  const retryTimer = useRef(null);
  const isMounted = useRef(true);

  async function startWebcam() {
    // Step 1: get webcam first — only then open WebSocket
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        // Wait for video metadata so the frame canvas has real dimensions
        await new Promise((res) => {
          videoRef.current.onloadedmetadata = res;
        });
      }
      // Reset error state on success
      setCamError(null);
      // Step 2: webcam is ready — NOW connect WebSocket
      connectWebSocket();
    } catch (err) {
      setCamError("Camera access denied. Enable webcam for emotion detection.");
    }
  }

  function connectWebSocket() {
    if (!isMounted.current) return;

    // Don't open a second connection if one is already live
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMounted.current) { ws.close(); return; }
      retryCount.current = 0;          // reset retry counter on clean connect
      setCamError(null);
      // Start sending frames only after connection confirmed open
      clearInterval(captureRef.current);
      captureRef.current = setInterval(() => sendFrame(ws), FRAME_INTERVAL_MS);
    };

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === "emotion_result") {
          setEmotion(msg.data.emotion);
          setConfidence(msg.data.confidence);
          setFaceDetected(msg.data.face_detected);
        }
      } catch (_) { /* ignore malformed messages */ }
    };

    ws.onerror = () => {
      // onerror fires before onclose — just log it, let onclose handle retry
      // Do NOT show error message here — it fires on transient issues too
    };

    ws.onclose = (evt) => {
      clearInterval(captureRef.current);
      if (!isMounted.current) return;

      // Only retry if the webcam stream is still active (user didn't leave page)
      if (!streamRef.current) return;

      if (retryCount.current < WS_MAX_RETRIES) {
        retryCount.current += 1;
        const delay = WS_RETRY_DELAY_MS * retryCount.current;
        setCamError(`Reconnecting to emotion server… (attempt ${retryCount.current}/${WS_MAX_RETRIES})`);
        retryTimer.current = setTimeout(() => {
          if (isMounted.current) connectWebSocket();
        }, delay);
      } else {
        // All retries exhausted — switch to REST polling fallback
        setCamError("Emotion server unreachable. Check that api_server.py is running on port 8000.");
        startRestFallback();
      }
    };
  }

  // REST fallback: poll /api/analyze-emotion every 2s when WebSocket fails
  function startRestFallback() {
    clearInterval(captureRef.current);
    captureRef.current = setInterval(async () => {
      if (!videoRef.current || !canvasRef.current || !streamRef.current) return;
      try {
        const ctx = canvasRef.current.getContext("2d");
        canvasRef.current.width = 320;
        canvasRef.current.height = 240;
        ctx.drawImage(videoRef.current, 0, 0, 320, 240);
        const b64 = canvasRef.current.toDataURL("image/jpeg", 0.7).split(",")[1];
        const result = await API.analyzeEmotion(b64, sessionId);
        if (result.face_detected) {
          setEmotion(result.emotion);
          setConfidence(result.confidence);
          setFaceDetected(true);
        } else {
          setFaceDetected(false);
        }
      } catch (_) { /* server still down — stay silent */ }
    }, 2000);
  }

  function stopWebcam() {
    isMounted.current = false;
    clearInterval(captureRef.current);
    clearTimeout(retryTimer.current);
    wsRef.current?.close();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }

  function sendFrame(ws) {
    if (!videoRef.current || !canvasRef.current) return;
    if (ws.readyState !== WebSocket.OPEN) return;
    // Make sure video has real dimensions before capturing
    if (videoRef.current.videoWidth === 0) return;
    const ctx = canvasRef.current.getContext("2d");
    canvasRef.current.width = 320;
    canvasRef.current.height = 240;
    ctx.drawImage(videoRef.current, 0, 0, 320, 240);
    const b64 = canvasRef.current.toDataURL("image/jpeg", 0.7).split(",")[1];
    ws.send(JSON.stringify({ type: "frame", image: b64 }));
  }

  // ── Run code ──────────────────────────────────────────────────────────────
  async function runCode() {
    if (!problem || !code.trim()) return;
    setRunning(true);
    setTestResults(null);
    try {
      const result = await API.executeCode(code, problem.problem_id, sessionId);
      setTestResults(result);
    } catch (e) {
      setTestResults({ success: false, all_passed: false, test_results: [], error: String(e) });
    } finally {
      setRunning(false);
    }
  }

  // ── Submit ────────────────────────────────────────────────────────────────
  async function submitSolution() {
    if (!testResults?.all_passed) return;
    setSubmitting(true);
    try {
      const result = await API.submitSolution(problem.problem_id, code, sessionId);
      setSolved(true);
      setSolveMsg(result);
      setDifficulty(result.difficulty_change?.new_difficulty || difficulty);
    } catch (e) {
      console.error("Submit failed:", e);
    } finally {
      setSubmitting(false);
    }
  }

  // ── Hint ──────────────────────────────────────────────────────────────────
  async function getHint() {
    setHintLoading(true);
    try {
      const h = await API.getHint(sessionId);
      if (h.hint_available) setHints((prev) => [...prev, h]);
    } finally {
      setHintLoading(false);
    }
  }

  const diffColor = { EASY: "#00e5a0", MEDIUM: "#f5c542", HARD: "#ff5c5c" };

  return (
    <div className="lab-layout">

      {/* ── Top Bar ── */}
      <header className="lab-header">
        <div className="lab-logo">FC</div>
        <div className="lab-nav">
          <span className="diff-badge" style={{ background: diffColor[difficulty] ?? "#888" }}>
            {difficulty}
          </span>
          <button className="nav-btn" onClick={() => loadProblem()}>New Problem</button>
          <button className="nav-btn" onClick={onGoAnalytics}>Analytics →</button>
        </div>
      </header>

      <div className="lab-body">

        {/* ── Left: Problem + Editor ── */}
        <div className="lab-left">

          {/* Problem Card */}
          {problem ? (
            <div className="problem-card">
              <div className="problem-meta">
                <span className="problem-category">{problem.category}</span>
                <span className="problem-id">#{problem.problem_id}</span>
              </div>
              <h2 className="problem-title">{problem.title}</h2>
              <pre className="problem-desc">{problem.description}</pre>

              {/* Test cases preview */}
              <div className="tc-preview">
                {problem.test_cases?.slice(0, 2).map((tc, i) => (
                  <div key={i} className="tc-row">
                    <span className="tc-key">Example {i + 1}</span>
                    <code>Input: {JSON.stringify(tc.input)} → {JSON.stringify(tc.expected)}</code>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="problem-loading">Loading problem…</div>
          )}

          {/* Code Editor */}
          <div className="editor-section">
            <div className="editor-toolbar">
              <span className="editor-lang">Python</span>
              <div className="editor-actions">
                <button className="btn-run" onClick={runCode} disabled={running}>
                  {running ? "Running…" : "▶  Run"}
                </button>
                <button
                  className="btn-submit"
                  onClick={submitSolution}
                  disabled={!testResults?.all_passed || submitting || solved}
                >
                  {submitting ? "Submitting…" : "✓  Submit"}
                </button>
                <button className="btn-hint" onClick={getHint} disabled={hintLoading}>
                  {hintLoading ? "…" : "💡 Hint"}
                </button>
                <button
                  className="btn-reset"
                  onClick={() => { setCode(problem?.starter_code || ""); setTestResults(null); }}
                >
                  Reset
                </button>
              </div>
            </div>
            <CodeEditor value={code} onChange={setCode} />
          </div>

          {/* Results */}
          <TestResults results={testResults} />

          {/* Solved banner */}
          {solved && solveMsg && (
            <div className="solved-banner">
              <h3>🎉 Solved!</h3>
              <p>Time: {solveMsg.time_spent?.toFixed(0)}s · Avg confidence: {(solveMsg.avg_confidence * 100).toFixed(0)}%</p>
              <p className="diff-change">
                Difficulty: {solveMsg.difficulty_change?.old_difficulty} →{" "}
                <strong style={{ color: diffColor[solveMsg.difficulty_change?.new_difficulty] }}>
                  {solveMsg.difficulty_change?.new_difficulty}
                </strong>
                &nbsp;({solveMsg.difficulty_change?.adjustment})
              </p>
              <p className="diff-reason">{solveMsg.difficulty_change?.reason}</p>
              <button className="btn-next" onClick={() => loadProblem()}>Next Problem →</button>
            </div>
          )}

          {/* Hints */}
          {hints.length > 0 && (
            <div className="hints-section">
              <h4>Hints</h4>
              {hints.map((h, i) => (
                <div key={i} className="hint-card">
                  <span className="hint-level">{h.hint_level}</span>
                  <p>{h.hint_text}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Right: Webcam + Emotion Panel ── */}
        <div className="lab-right">

          <div className="cam-panel">
            <div className="cam-header">
              <span className={`face-indicator ${faceDetected ? "active" : ""}`} />
              <span>{faceDetected ? "Face detected" : "No face"}</span>
            </div>

            <div className="cam-feed-wrap">
              <video ref={videoRef} autoPlay muted playsInline className="cam-feed" />
              <canvas ref={canvasRef} style={{ display: "none" }} />
              {camError && <div className="cam-overlay">{camError}</div>}
            </div>

            <div className="emotion-row">
              <span className="emotion-emoji">{EMOTION_EMOJI[emotion] ?? "😐"}</span>
              <div className="emotion-info">
                <span className="emotion-label">{emotion.toUpperCase()}</span>
                <span className="emotion-sub">Current emotion</span>
              </div>
            </div>

            <ConfidenceRing value={confidence} />

            <div className="conf-bands">
              {[
                { label: "Low", range: "0–35%", color: "#ff5c5c", active: confidence < 0.35 },
                { label: "Medium", range: "35–70%", color: "#f5c542", active: confidence >= 0.35 && confidence < 0.7 },
                { label: "High", range: "70–100%", color: "#00e5a0", active: confidence >= 0.7 },
              ].map((b) => (
                <div key={b.label} className={`conf-band ${b.active ? "active" : ""}`}>
                  <span style={{ background: b.color }} className="band-dot" />
                  <span>{b.label}</span>
                  <span className="band-range">{b.range}</span>
                </div>
              ))}
            </div>

            {/* Auto-hint warning */}
            {confidence < 0.35 && faceDetected && (
              <div className="auto-hint-warn">
                ⚠️ Low confidence detected. Try requesting a hint!
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
