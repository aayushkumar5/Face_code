import { useEffect, useState } from "react";
import Home from "./pages/Home";
import CodingLab from "./pages/CodingLab";
import Analytics from "./pages/Analytics";
import { API, setSessionToken } from "./api";
import "./styles.css";

function loadStoredCredential() {
  try {
    const value = JSON.parse(sessionStorage.getItem("facecode_credential"));
    if (value?.token && value?.expires_at > Date.now() / 1000) {
      setSessionToken(value.token);
      return value;
    }
  } catch (_) {
    sessionStorage.removeItem("facecode_credential");
  }
  return null;
}

export default function App() {
  const [screen, setScreen] = useState("home");
  const [credential, setCredential] = useState(loadStoredCredential);
  const [startupError, setStartupError] = useState(null);

  useEffect(() => {
    if (credential) return;
    API.createSession()
      .then((value) => {
        setSessionToken(value.token);
        sessionStorage.setItem("facecode_credential", JSON.stringify(value));
        setCredential(value);
      })
      .catch((error) => setStartupError(String(error)));
  }, [credential]);

  if (startupError) {
    return <div className="app-root">Unable to start a secure session: {startupError}</div>;
  }
  if (!credential) {
    return <div className="app-root">Starting FaceCode...</div>;
  }

  return (
    <div className="app-root">
      {screen === "home" && <Home onStart={() => setScreen("lab")} />}
      {screen === "lab" && (
        <CodingLab
          sessionId={credential.session_id}
          sessionToken={credential.token}
          onGoAnalytics={() => setScreen("analytics")}
        />
      )}
      {screen === "analytics" && (
        <Analytics
          sessionId={credential.session_id}
          onBack={() => setScreen("lab")}
        />
      )}
    </div>
  );
}
