import { useState } from "react";

export default function Home({ onStart }) {
  const [hovering, setHovering] = useState(false);

  return (
    <div className="home-page">
      {/* Animated background grid */}
      <div className="bg-grid" />
      <div className="bg-glow" />

      <div className="home-content">
        <div className="logo-mark">FC</div>

        <h1 className="home-title">
          <span className="title-face">Face</span>
          <span className="title-code">Code</span>
        </h1>

        <p className="home-subtitle">
          Adaptive AI coding challenges that read your face.<br />
          The harder you find it, the more it helps.
        </p>

        <div className="feature-row">
          {[
            { icon: "◉", label: "Emotion Detection", desc: "CNN reads your confidence in real-time" },
            { icon: "⬡", label: "Adaptive Difficulty", desc: "Problems adjust to your performance" },
            { icon: "◈", label: "Smart Hints", desc: "Contextual help when you need it" },
          ].map((f) => (
            <div className="feature-card" key={f.label}>
              <span className="feature-icon">{f.icon}</span>
              <strong>{f.label}</strong>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>

        <button
          className={`start-btn ${hovering ? "hovered" : ""}`}
          onMouseEnter={() => setHovering(true)}
          onMouseLeave={() => setHovering(false)}
          onClick={onStart}
        >
          <span>Start Coding</span>
          <span className="btn-arrow">→</span>
        </button>

        <p className="home-note">
          Allow webcam access when prompted for full adaptive experience.
        </p>
      </div>
    </div>
  );
}
