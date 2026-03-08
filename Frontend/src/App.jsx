import { useState } from "react";
import Home from "./pages/Home";
import CodingLab from "./pages/CodingLab";
import Analytics from "./pages/Analytics";
import "./styles.css";

// Simple session ID — in production, tie to auth
const SESSION_ID = `session_${Date.now()}`;

export default function App() {
  const [screen, setScreen] = useState("home"); // "home" | "lab" | "analytics"

  return (
    <div className="app-root">
      {screen === "home" && (
        <Home onStart={() => setScreen("lab")} />
      )}
      {screen === "lab" && (
        <CodingLab
          sessionId={SESSION_ID}
          onGoAnalytics={() => setScreen("analytics")}
        />
      )}
      {screen === "analytics" && (
        <Analytics
          sessionId={SESSION_ID}
          onBack={() => setScreen("lab")}
        />
      )}
    </div>
  );
}
