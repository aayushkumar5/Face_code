import { useState, useEffect } from "react";
import { API } from "../api";

// ── Simple bar chart (pure SVG, no library needed) ─────────────────────────
function BarChart({ data, labelKey, valueKey, color = "#00e5a0", title }) {
  if (!data?.length) return <div className="chart-empty">No data yet</div>;
  const max = Math.max(...data.map((d) => d[valueKey]), 1);
  return (
    <div className="bar-chart">
      {title && <h4 className="chart-title">{title}</h4>}
      <svg width="100%" height="140" viewBox={`0 0 ${data.length * 60} 140`} preserveAspectRatio="none">
        {data.map((d, i) => {
          const h = Math.max((d[valueKey] / max) * 100, 2);
          return (
            <g key={i}>
              <rect
                x={i * 60 + 8} y={110 - h} width={44} height={h}
                fill={color} rx="4" opacity="0.85"
              />
              <text x={i * 60 + 30} y={128} textAnchor="middle" fontSize="10" fill="#888">
                {String(d[labelKey]).substring(0, 5)}
              </text>
              <text x={i * 60 + 30} y={104 - h} textAnchor="middle" fontSize="10" fill={color}>
                {d[valueKey]}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ── Stat card ──────────────────────────────────────────────────────────────
function StatCard({ label, value, sub, color = "#00e5a0" }) {
  return (
    <div className="stat-card">
      <div className="stat-value" style={{ color }}>{value}</div>
      <div className="stat-label">{label}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

// ── Main Analytics ─────────────────────────────────────────────────────────
export default function Analytics({ sessionId, onBack }) {
  const [stats, setStats] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [s, sess] = await Promise.all([
          API.getAnalytics(),
          API.getSessionStats(sessionId),
        ]);
        setStats(s);
        setSession(sess?.stats);
      } catch (e) {
        console.error("Analytics load error:", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [sessionId]);

  // Build category breakdown from stats if available
  const categoryData = stats?.category_breakdown
    ? Object.entries(stats.category_breakdown).map(([k, v]) => ({ label: k, value: v }))
    : [];

  const diffData = stats?.difficulty_breakdown
    ? Object.entries(stats.difficulty_breakdown).map(([k, v]) => ({ label: k, value: v }))
    : [];

  const diffColor = { EASY: "#00e5a0", MEDIUM: "#f5c542", HARD: "#ff5c5c" };
  const currentDiff = session?.current_difficulty || "EASY";

  return (
    <div className="analytics-page">
      <div className="analytics-header">
        <button className="back-btn" onClick={onBack}>← Back to Lab</button>
        <h1 className="analytics-title">Analytics</h1>
        <span className="diff-badge" style={{ background: diffColor[currentDiff] }}>
          {currentDiff}
        </span>
      </div>

      {loading ? (
        <div className="analytics-loading">
          <div className="spinner" />
          <span>Loading analytics…</span>
        </div>
      ) : (
        <div className="analytics-body">

          {/* Current Session */}
          <section className="analytics-section">
            <h2 className="section-title">Current Session</h2>
            <div className="stat-grid">
              <StatCard label="Attempted" value={session?.total_attempted ?? 0} color="#7c9fff" />
              <StatCard label="Solved" value={session?.total_solved ?? 0} color="#00e5a0" />
              <StatCard
                label="Success Rate"
                value={`${session?.success_rate?.toFixed(0) ?? 0}%`}
                color={session?.success_rate > 60 ? "#00e5a0" : "#f5c542"}
              />
              <StatCard
                label="Avg Confidence"
                value={`${((session?.avg_confidence ?? 0.5) * 100).toFixed(0)}%`}
                color="#f5c542"
              />
              <StatCard
                label="Avg Solve Time"
                value={`${session?.avg_solve_time?.toFixed(0) ?? 0}s`}
                sub="per problem"
                color="#7c9fff"
              />
              <StatCard
                label="Hints Used"
                value={session?.total_hints_used ?? 0}
                sub={`${session?.hints_per_problem?.toFixed(1) ?? 0} per problem`}
                color="#ff9c5c"
              />
            </div>
          </section>

          {/* All-Time Stats */}
          <section className="analytics-section">
            <h2 className="section-title">All-Time Stats</h2>
            <div className="stat-grid">
              <StatCard label="Total Sessions" value={stats?.total_sessions ?? 0} color="#7c9fff" />
              <StatCard label="Total Solved" value={stats?.total_solved ?? 0} color="#00e5a0" />
              <StatCard
                label="Overall Rate"
                value={`${stats?.solve_rate?.toFixed(0) ?? 0}%`}
                color={stats?.solve_rate > 60 ? "#00e5a0" : "#f5c542"}
              />
              <StatCard
                label="Avg Confidence"
                value={`${((stats?.avg_confidence ?? 0.5) * 100).toFixed(0)}%`}
                color="#f5c542"
              />
            </div>
          </section>

          {/* Charts row */}
          <div className="charts-row">
            {diffData.length > 0 && (
              <section className="analytics-section chart-section">
                <BarChart
                  data={diffData} labelKey="label" valueKey="value"
                  color="#7c9fff" title="Problems by Difficulty"
                />
              </section>
            )}
            {categoryData.length > 0 && (
              <section className="analytics-section chart-section">
                <BarChart
                  data={categoryData} labelKey="label" valueKey="value"
                  color="#00e5a0" title="Problems by Category"
                />
              </section>
            )}
          </div>

          {/* Emotion breakdown */}
          {stats?.emotion_breakdown && (
            <section className="analytics-section">
              <h2 className="section-title">Emotion Distribution</h2>
              <div className="emotion-breakdown">
                {Object.entries(stats.emotion_breakdown)
                  .sort((a, b) => b[1] - a[1])
                  .map(([emotion, count]) => {
                    const total = Object.values(stats.emotion_breakdown).reduce((a, b) => a + b, 0);
                    const pct = total > 0 ? (count / total * 100).toFixed(1) : 0;
                    return (
                      <div key={emotion} className="emotion-bar-row">
                        <span className="em-label">{emotion}</span>
                        <div className="em-bar-track">
                          <div
                            className="em-bar-fill"
                            style={{ width: `${pct}%`, background: "#7c9fff" }}
                          />
                        </div>
                        <span className="em-pct">{pct}%</span>
                      </div>
                    );
                  })}
              </div>
            </section>
          )}

          {/* No data state */}
          {!stats?.total_sessions && (
            <div className="analytics-empty">
              <span>📊</span>
              <p>No session data yet. Solve some problems to see your analytics!</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
