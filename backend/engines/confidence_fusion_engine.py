"""
FaceCode - ML-Based Confidence Fusion Engine
Replaces the simple weighted average with a learned fusion model.

Signal sources:
  1. Facial emotion probabilities   (7-dim from CNN)
  2. Emotion temporal dynamics       (velocity + entropy of last N frames)
  3. Behavioral signals              (typing speed, error rate, inactivity)
  4. Time-on-problem                 (normalised)

The fusion model is a small MLP trained with self-supervised labels derived
from ground-truth session outcomes (solved / not solved, hints used).

For production usage without a pre-trained fusion model it falls back to
a hand-crafted rule-based scorer that is already much richer than the
original weighted average.
"""

import numpy as np
import os
import json
import time
from collections import deque
from typing import Dict, Tuple, List, Optional


# ─────────────────────────────────────────────────────────────
# SIGNAL FEATURE EXTRACTOR
# ─────────────────────────────────────────────────────────────

EMOTION_LABELS = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]

# Base confidence contribution per emotion
_EMOTION_BASE = {
    "happy":    0.95,
    "neutral":  0.60,
    "surprise": 0.72,
    "sad":      0.25,
    "angry":    0.18,
    "fear":     0.10,
    "disgust":  0.20,
}


class SignalExtractor:
    """
    Maintains rolling windows of raw signals and extracts
    a fixed-length feature vector for the fusion model.
    """

    WINDOW = 30   # frames kept in emotion history

    def __init__(self):
        self._emotion_history: deque = deque(maxlen=self.WINDOW)
        self._confidence_history: deque = deque(maxlen=100)
        self.reset_behavior()

    # ── Behavior tracking ──────────────────────────────────

    def reset_behavior(self):
        self._last_activity = time.time()
        self._typing_events: deque = deque(maxlen=60)
        self._error_count   = 0
        self._attempt_count = 0
        self._problem_start = time.time()

    def record_keystroke(self):
        now = time.time()
        self._last_activity = now
        self._typing_events.append(now)

    def record_run(self, passed: bool):
        self._attempt_count += 1
        if not passed:
            self._error_count += 1
        self._last_activity = time.time()

    # ── Emotion push ───────────────────────────────────────

    def push_emotion(self, probs: Dict[str, float]):
        """
        Push a new emotion probability dict (from CNN).
        Converts to ordered numpy array matching EMOTION_LABELS.
        """
        vec = np.array([probs.get(e, 0.0) for e in EMOTION_LABELS], dtype=np.float32)
        self._emotion_history.append(vec)

    # ── Feature vector ─────────────────────────────────────

    def extract(self) -> np.ndarray:
        """
        Extract a 22-dimensional feature vector:
          [0:7]   mean emotion probabilities over window
          [7:14]  std  emotion probabilities over window
          [14]    emotion entropy (uncertainty measure)
          [15]    dominant-emotion base confidence
          [16]    emotion velocity (how fast dominant emotion changes)
          [17]    typing speed (keys/min, normalised 0-1)
          [18]    error rate
          [19]    inactivity score (0=active, 1=very inactive)
          [20]    time on problem (normalised, capped at 1)
          [21]    success rate so far
        """
        feats = np.zeros(22, dtype=np.float32)

        # ─ emotion features ─
        if self._emotion_history:
            history = np.stack(self._emotion_history)          # (N, 7)
            mean_probs = history.mean(axis=0)                  # (7,)
            std_probs  = history.std(axis=0)                   # (7,)
            feats[0:7]  = mean_probs
            feats[7:14] = std_probs

            # Shannon entropy (normalised 0-1)
            p = np.clip(mean_probs, 1e-9, 1.0)
            entropy = -np.sum(p * np.log(p))
            feats[14] = entropy / np.log(7)   # max entropy = ln(7)

            # Dominant emotion base confidence
            dominant = EMOTION_LABELS[np.argmax(mean_probs)]
            feats[15] = _EMOTION_BASE.get(dominant, 0.5)

            # Velocity: fraction of recent frames where dominant changed
            if len(history) >= 5:
                dominants = [EMOTION_LABELS[np.argmax(h)] for h in history[-10:]]
                changes = sum(a != b for a, b in zip(dominants, dominants[1:]))
                feats[16] = changes / max(len(dominants) - 1, 1)
            else:
                feats[16] = 0.0
        else:
            feats[15] = 0.5  # neutral default

        # ─ behavioral features ─
        now = time.time()

        # Typing speed: keystrokes in last 60s, normalised (cap at 120 KPM = 1.0)
        recent_keys = sum(1 for t in self._typing_events if now - t < 60)
        feats[17] = min(recent_keys / 120.0, 1.0)

        # Error rate
        if self._attempt_count > 0:
            feats[18] = self._error_count / self._attempt_count
        else:
            feats[18] = 0.0

        # Inactivity (0 = just active, 1 = 120+ seconds inactive)
        inactivity = now - self._last_activity
        feats[19] = min(inactivity / 120.0, 1.0)

        # Time on problem (normalised; 600s = 1.0)
        time_on = now - self._problem_start
        feats[20] = min(time_on / 600.0, 1.0)

        # Success rate
        if self._attempt_count > 0:
            successes = self._attempt_count - self._error_count
            feats[21] = successes / self._attempt_count
        else:
            feats[21] = 0.5

        return feats


# ─────────────────────────────────────────────────────────────
# RULE-BASED FUSION (always available, no model needed)
# ─────────────────────────────────────────────────────────────

def rule_based_confidence(feats: np.ndarray) -> float:
    """
    Interpretable rule-based confidence score from feature vector.
    Used as fallback when no ML model is loaded.
    """
    emotion_conf  = feats[15]          # base confidence of dominant emotion
    uncertainty   = feats[14]          # entropy (high = model unsure)
    velocity      = feats[16]          # emotion flipping (high = unstable)
    typing_score  = feats[17]          # active typing = good
    error_rate    = feats[18]          # high errors = low confidence
    inactivity    = feats[19]          # stuck = low confidence
    success_rate  = feats[21]          # recent run successes

    # Penalise high uncertainty and instability
    emotion_score = emotion_conf * (1 - 0.3 * uncertainty) * (1 - 0.2 * velocity)

    # Behavioral score
    behavior_score = (
        0.35 * typing_score +
        0.35 * (1 - error_rate) +
        0.20 * (1 - inactivity) +
        0.10 * success_rate
    )

    # Weighted fusion
    confidence = 0.45 * emotion_score + 0.55 * behavior_score
    return float(np.clip(confidence, 0.0, 1.0))


# ─────────────────────────────────────────────────────────────
# ML FUSION MODEL
# ─────────────────────────────────────────────────────────────

class FusionMLP:
    """
    Small MLP that learns to predict confidence from the 22-dim feature vector.

    Training target: outcome score derived from session data
      outcome = 1.0  if solved quickly with no hints
      outcome = 0.5  if solved slowly or with hints
      outcome = 0.0  if not solved

    The model can be trained offline on logged session data then saved
    as 'models/fusion_mlp.npz' (pure numpy, no TF needed at runtime).
    """

    LAYERS = [22, 64, 32, 1]   # input → hidden → hidden → output

    def __init__(self):
        self.weights: Optional[List[np.ndarray]] = None
        self.biases:  Optional[List[np.ndarray]] = None

    # ── Forward pass (numpy only) ──────────────────────────

    def predict(self, x: np.ndarray) -> float:
        if self.weights is None:
            return -1.0  # signal not loaded
        h = x.copy()
        for W, b in zip(self.weights[:-1], self.biases[:-1]):
            h = np.maximum(0, h @ W + b)     # ReLU
        out = h @ self.weights[-1] + self.biases[-1]
        return float(np.clip(out[0], 0.0, 1.0))   # sigmoid-like clamp

    # ── Save / Load ────────────────────────────────────────

    def save(self, path: str = "models/fusion_mlp.npz"):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        data = {}
        for i, (W, b) in enumerate(zip(self.weights, self.biases)):
            data[f"W{i}"] = W
            data[f"b{i}"] = b
        np.savez(path, **data)
        print(f"✅ Fusion MLP saved to {path}")

    def load(self, path: str = "models/fusion_mlp.npz") -> bool:
        if not os.path.exists(path):
            return False
        data = np.load(path)
        n_layers = len(self.LAYERS) - 1
        self.weights = [data[f"W{i}"] for i in range(n_layers)]
        self.biases  = [data[f"b{i}"] for i in range(n_layers)]
        print(f"✅ Fusion MLP loaded from {path}")
        return True

    # ── Training (offline, uses numpy SGD) ─────────────────

    def train_offline(
        self,
        session_log_path: str,
        epochs: int = 200,
        lr: float = 0.01,
        save_path: str = "models/fusion_mlp.npz"
    ):
        """
        Train the fusion MLP on historical session logs.

        Log format (JSON lines):
          {"features": [...22 floats...], "outcome": 0.8}

        Generates synthetic training data if log file is missing
        (useful for initial development / demo).
        """
        X, y = self._load_or_generate(session_log_path)
        print(f"🔢 Training FusionMLP on {len(X)} samples ...")

        # Xavier initialisation
        np.random.seed(42)
        self.weights = []
        self.biases  = []
        for in_dim, out_dim in zip(self.LAYERS, self.LAYERS[1:]):
            scale = np.sqrt(2.0 / in_dim)
            self.weights.append(np.random.randn(in_dim, out_dim).astype(np.float32) * scale)
            self.biases.append(np.zeros(out_dim, dtype=np.float32))

        # Mini-batch SGD
        batch_size = 32
        for epoch in range(epochs):
            idx = np.random.permutation(len(X))
            total_loss = 0.0
            for start in range(0, len(X), batch_size):
                batch_idx = idx[start:start + batch_size]
                xb = X[batch_idx]
                yb = y[batch_idx]

                # Forward
                activations = [xb]
                h = xb
                for W, b in zip(self.weights[:-1], self.biases[:-1]):
                    h = np.maximum(0, h @ W + b)
                    activations.append(h)
                out = h @ self.weights[-1] + self.biases[-1]
                pred = np.clip(out, 0.0, 1.0)

                # MSE loss
                diff = pred - yb.reshape(-1, 1)
                total_loss += np.mean(diff ** 2)

                # Backprop (simplified)
                grad = 2 * diff / len(xb)
                dW = activations[-1].T @ grad
                db = grad.sum(axis=0)
                self.weights[-1] -= lr * dW
                self.biases[-1]  -= lr * db

            if (epoch + 1) % 50 == 0:
                print(f"  Epoch {epoch+1:3d}/{epochs} | Loss: {total_loss:.4f}")

        self.save(save_path)

    def _load_or_generate(self, path: str) -> Tuple[np.ndarray, np.ndarray]:
        """Load session log or generate synthetic data."""
        if os.path.exists(path):
            samples = []
            with open(path) as f:
                for line in f:
                    obj = json.loads(line.strip())
                    samples.append((obj["features"], obj["outcome"]))
            X = np.array([s[0] for s in samples], dtype=np.float32)
            y = np.array([s[1] for s in samples], dtype=np.float32)
            return X, y

        print("⚠️  No session log found – generating synthetic training data")
        np.random.seed(0)
        N = 2000
        X = np.random.rand(N, 22).astype(np.float32)
        # Synthetic rule: high emotion conf + active typing + low errors = high conf
        y = (0.35 * X[:, 15] +          # emotion confidence base
             0.25 * X[:, 17] +          # typing speed
             0.25 * (1 - X[:, 18]) +    # low error rate
             0.15 * (1 - X[:, 19])      # not inactive
             ).astype(np.float32)
        y = np.clip(y + np.random.randn(N).astype(np.float32) * 0.05, 0, 1)
        return X, y


# ─────────────────────────────────────────────────────────────
# MAIN CONFIDENCE ENGINE  (public API)
# ─────────────────────────────────────────────────────────────

class ConfidenceFusionEngine:
    """
    Drop-in replacement for the original ConfidenceCalculator.

    Usage:
        engine = ConfidenceFusionEngine()
        engine.extractor.push_emotion(cnn_probs_dict)
        engine.extractor.record_keystroke()
        engine.extractor.record_run(passed=False)

        confidence = engine.get_confidence()     # 0–1 float
        label      = engine.get_label()          # "High" / "Medium" / "Low"
        hint_now   = engine.should_hint()        # True/False
    """

    def __init__(self, model_path: str = "models/fusion_mlp.npz"):
        self.extractor = SignalExtractor()
        self._mlp = FusionMLP()
        self._use_ml = self._mlp.load(model_path)
        self._history: deque = deque(maxlen=100)

    # ── Core API ───────────────────────────────────────────

    def get_confidence(self) -> float:
        feats = self.extractor.extract()
        if self._use_ml:
            score = self._mlp.predict(feats)
            if score < 0:                # model returned error signal
                score = rule_based_confidence(feats)
        else:
            score = rule_based_confidence(feats)
        self._history.append(score)
        return score

    def get_average_confidence(self, n: int = 10) -> float:
        if not self._history:
            return 0.5
        recent = list(self._history)[-n:]
        return float(np.mean(recent))

    def get_label(self) -> str:
        c = self.get_confidence()
        if c >= 0.70:  return "High"
        if c >= 0.40:  return "Medium"
        return "Low"

    def should_hint(self) -> bool:
        """True when learner has been struggling for a sustained period."""
        feats = self.extractor.extract()
        c = rule_based_confidence(feats)   # always use interpretable rules here

        low_conf_sustained = c < 0.35 and feats[20] > 0.15   # >90s on problem
        stuck              = feats[19] > 0.375                 # >45s inactivity
        many_errors        = feats[18] > 0.6 and feats[20] > 0.1

        return low_conf_sustained or stuck or many_errors

    def get_debug_info(self) -> Dict:
        feats = self.extractor.extract()
        return {
            "dominant_emotion_base_conf": round(float(feats[15]), 3),
            "emotion_entropy":            round(float(feats[14]), 3),
            "emotion_velocity":           round(float(feats[16]), 3),
            "typing_speed_norm":          round(float(feats[17]), 3),
            "error_rate":                 round(float(feats[18]), 3),
            "inactivity_norm":            round(float(feats[19]), 3),
            "time_on_problem_norm":       round(float(feats[20]), 3),
            "ml_model_active":            self._use_ml,
            "current_confidence":         round(self.get_confidence(), 3),
            "label":                      self.get_label(),
        }


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FaceCode Confidence Fusion Engine")
    parser.add_argument("--train-fusion", metavar="LOG_PATH",
                        help="Train fusion MLP on session log (JSON lines). "
                             "Generates synthetic data if path doesn't exist.")
    parser.add_argument("--demo", action="store_true",
                        help="Run a quick simulation demo")
    args = parser.parse_args()

    if args.train_fusion is not None:
        mlp = FusionMLP()
        mlp.train_offline(args.train_fusion)

    if args.demo:
        print("=" * 60)
        print("Confidence Fusion Engine – Demo Simulation")
        print("=" * 60)

        engine = ConfidenceFusionEngine()

        # Simulate a session
        scenarios = [
            ("Focused, fast typing",        {"happy": 0.6, "neutral": 0.3}, True,  False),
            ("Confused, slow typing",       {"fear": 0.4, "sad": 0.3},       False, False),
            ("Neutral, moderate activity",  {"neutral": 0.7, "happy": 0.2},  True,  False),
            ("Stressed, no activity",       {"angry": 0.5, "fear": 0.3},     False, True),
        ]

        for label, probs, ran_code, inactive in scenarios:
            engine.extractor.push_emotion(probs)
            if ran_code:
                engine.extractor.record_run(passed=False)
            if not inactive:
                for _ in range(20):
                    engine.extractor.record_keystroke()

            conf = engine.get_confidence()
            info = engine.get_debug_info()
            print(f"\n🎬 {label}")
            print(f"   Confidence : {conf:.3f} → {engine.get_label()}")
            print(f"   Hint needed: {engine.should_hint()}")
            print(f"   Signals    : emotion_base={info['dominant_emotion_base_conf']}, "
                  f"typing={info['typing_speed_norm']:.2f}, "
                  f"errors={info['error_rate']:.2f}")

        print("\n✅ Demo complete.")
