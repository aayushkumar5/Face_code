"""
FaceCode V3 - Emotion Engine (Updated)
Integrates custom CNN model; falls back to DeepFace if CNN not found.
Drop-in replacement for emotion_engine_improved.py
"""

import cv2
import numpy as np
from collections import deque
import time
import os
from typing import Dict, Optional, Tuple

# Our new ML modules
EMOTION_LABELS = ['angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral']

try:
    from emotion_cnn_model import EmotionCNNInference
    _CNN_MODULE_AVAILABLE = True
except ImportError:
    _CNN_MODULE_AVAILABLE = False

try:
    from confidence_fusion_engine import ConfidenceFusionEngine, SignalExtractor
    _FUSION_MODULE_AVAILABLE = True
except ImportError:
    _FUSION_MODULE_AVAILABLE = False


EMOTION_CONFIDENCE_MAP = {
    'happy':    0.95,
    'neutral':  0.60,
    'surprise': 0.72,
    'sad':      0.25,
    'angry':    0.15,
    'fear':     0.10,
    'disgust':  0.20,
}


class EmotionEngine:
    """
    V3 Emotion Engine.

    Priority order for inference backend:
      1. Custom CNN  (emotion_cnn_model.py – fastest, domain-tuned)
      2. DeepFace    (richer but heavier; auto-detected)
      3. Dummy mode  (random; for UI testing without any model)
    """

    def __init__(
        self,
        buffer_size: int = 10,
        cnn_model_path: str = "model/emotion_cnn.keras",
        model_cache_dir: str = "model"
    ):
        self.buffer_size    = buffer_size
        self.emotion_buffer = deque(maxlen=buffer_size)
        self.cnn_model_path = cnn_model_path

        os.makedirs(model_cache_dir, exist_ok=True)

        # Face detection (OpenCV Haar Cascade)
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

        # ── Backend selection ──────────────────────────────
        self.backend       = "dummy"
        self._cnn: Optional[EmotionCNNInference] = None
        self.DeepFace      = None
        self.deepface_available = False

        if _CNN_MODULE_AVAILABLE and os.path.exists(cnn_model_path):
            self._cnn = EmotionCNNInference(cnn_model_path)
            if self._cnn.available:
                self.backend = "cnn"
                print(f"✅ Using custom CNN: {cnn_model_path}")
        
        if self.backend == "dummy":
            try:
                from deepface import DeepFace
                self.DeepFace = DeepFace
                self.DeepFace.build_model("Emotion")
                self.backend = "deepface"
                self.deepface_available = True
                print("✅ Using DeepFace backend")
            except Exception:
                print("⚠️  No CNN model and DeepFace unavailable – using dummy mode")

        # ── Throttling ─────────────────────────────────────
        self.last_analysis_time = 0
        self.analysis_interval  = 0.8 if self.backend == "cnn" else 1.2

    # ──────────────────────────────────────────────────────
    # FACE DETECTION
    # ──────────────────────────────────────────────────────

    def detect_face(self, frame: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[tuple]]:
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.05, minNeighbors=4, minSize=(50, 50)
        )
        if len(faces) > 0:
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            pad = int(0.1 * w)
            x = max(0, x - pad)
            y = max(0, y - pad)
            w = min(frame.shape[1] - x, w + 2 * pad)
            h = min(frame.shape[0] - y, h + 2 * pad)
            return frame[y:y+h, x:x+w], (x, y, w, h)
        return None, None

    # ──────────────────────────────────────────────────────
    # EMOTION ANALYSIS (per-face)
    # ──────────────────────────────────────────────────────

    def analyze_emotion(self, face_bgr: np.ndarray) -> Optional[Dict]:
        now = time.time()
        if now - self.last_analysis_time < self.analysis_interval:
            return None

        result = None

        if self.backend == "cnn" and self._cnn:
            dominant, _, probs = self._cnn.predict_dominant(face_bgr)
            result = {
                "dominant_emotion": dominant,
                "emotion": {k: v * 100 for k, v in probs.items()}  # match DeepFace scale
            }

        elif self.backend == "deepface":
            try:
                # CLAHE pre-processing
                lab = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                clahe = cv2.createCLAHE(2.0, (8, 8))
                face_bgr = cv2.cvtColor(cv2.merge([clahe.apply(l), a, b]), cv2.COLOR_LAB2BGR)

                raw = self.DeepFace.analyze(
                    face_bgr, actions=["emotion"],
                    enforce_detection=False, silent=True,
                    detector_backend="opencv"
                )
                if isinstance(raw, list):
                    raw = raw[0]

                # Reduce neutral bias
                dominant = raw["dominant_emotion"]
                emotions = raw["emotion"]
                if dominant == "neutral":
                    others = {k: v for k, v in emotions.items() if k != "neutral"}
                    if others:
                        top = max(others, key=others.get)
                        if others[top] > emotions["neutral"] * 0.8:
                            dominant = top
                raw["dominant_emotion"] = dominant
                result = raw

            except Exception as e:
                print(f"⚠️  DeepFace error: {e}")

        else:  # dummy
            import random
            dominant = random.choice(["neutral", "happy", "sad", "surprise"])
            result = {
                "dominant_emotion": dominant,
                "emotion": {e: round(random.random() * 100, 1) for e in EMOTION_LABELS}
            }

        if result:
            self.last_analysis_time = now
        return result

    # ──────────────────────────────────────────────────────
    # SMOOTHING
    # ──────────────────────────────────────────────────────

    def get_smoothed_emotion(self) -> str:
        if not self.emotion_buffer:
            return "neutral"
        counts: Dict[str, int] = {}
        for e in self.emotion_buffer:
            counts[e] = counts.get(e, 0) + 1

        if "neutral" in counts and len(counts) > 1:
            others = {k: v for k, v in counts.items() if k != "neutral"}
            top_other = max(others, key=others.get)
            if others[top_other] >= counts["neutral"] * 0.3:
                return top_other

        return max(counts, key=counts.get)

    def emotion_to_confidence(self, emotion: str) -> float:
        return EMOTION_CONFIDENCE_MAP.get(emotion.lower(), 0.5)

    # ──────────────────────────────────────────────────────
    # MAIN: process_frame
    # ──────────────────────────────────────────────────────

    def process_frame(self, frame: np.ndarray) -> Dict:
        """
        Process a single webcam frame.

        Returns dict compatible with the original EmotionEngine interface
        PLUS a `raw_probs` key for the fusion engine.
        """
        result = {
            "face_detected":      False,
            "emotion":            "neutral",
            "emotion_confidence": 0.5,
            "raw_emotions":       None,
            "raw_probs":          None,   # normalised 0-1 dict (new)
            "annotated_frame":    frame.copy(),
        }

        face_region, face_coords = self.detect_face(frame)
        if face_region is None:
            cv2.putText(result["annotated_frame"],
                        "No face detected – position yourself",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            return result

        result["face_detected"] = True
        x, y, w, h = face_coords
        cv2.rectangle(result["annotated_frame"], (x, y), (x+w, y+h), (0, 255, 0), 3)

        analysis = self.analyze_emotion(face_region)
        if analysis:
            dominant = analysis["dominant_emotion"]
            self.emotion_buffer.append(dominant)
            smoothed   = self.get_smoothed_emotion()
            confidence = self.emotion_to_confidence(smoothed)

            result["emotion"]            = smoothed
            result["emotion_confidence"] = confidence
            result["raw_emotions"]       = analysis.get("emotion", {})

            # Normalised probs for fusion engine
            raw = analysis.get("emotion", {})
            total = sum(raw.values()) or 1
            result["raw_probs"] = {k: v / total for k, v in raw.items()}

            # HUD
            cv2.putText(result["annotated_frame"], smoothed.upper(),
                        (x, y - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            cv2.putText(result["annotated_frame"], f"Conf: {confidence:.2f}",
                        (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(result["annotated_frame"], f"Backend: {self.backend}",
                        (x, y + h + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

        return result

    def get_model_info(self) -> Dict:
        return {
            "backend":           self.backend,
            "deepface_available": self.deepface_available,
            "cnn_loaded":        self._cnn is not None and self._cnn.available if self._cnn else False,
            "cnn_model_path":    self.cnn_model_path,
            "analysis_interval": self.analysis_interval,
            "buffer_size":       self.buffer_size,
        }


# ─────────────────────────────────────────────────────────────
# BehaviorTracker and ConfidenceCalculator (updated to use fusion)
# ─────────────────────────────────────────────────────────────

class BehaviorTracker:
    """Thin wrapper – delegates to SignalExtractor when available."""

    def __init__(self):
        if _FUSION_MODULE_AVAILABLE:
            self._extractor = SignalExtractor()
        else:
            self._extractor = None
        self.error_count   = 0
        self.success_count = 0

    def reset(self):
        self.error_count   = 0
        self.success_count = 0
        if self._extractor:
            self._extractor.reset_behavior()

    def record_activity(self):
        if self._extractor:
            self._extractor.record_keystroke()

    def record_error(self):
        self.error_count += 1
        if self._extractor:
            self._extractor.record_run(passed=False)

    def record_success(self):
        self.success_count += 1
        if self._extractor:
            self._extractor.record_run(passed=True)

    def calculate_behavior_confidence(self) -> float:
        if self._extractor is None:
            return 0.5
        feats = self._extractor.extract()
        typing  = feats[17]
        errors  = feats[18]
        inact   = feats[19]
        return float(np.clip(
            0.35 * typing + 0.35 * (1 - errors) + 0.30 * (1 - inact),
            0.0, 1.0
        ))


class ConfidenceCalculator:
    """
    Upgraded: uses ConfidenceFusionEngine when available,
    otherwise falls back to the original weighted average.
    """

    def __init__(self):
        if _FUSION_MODULE_AVAILABLE:
            self._fusion = ConfidenceFusionEngine()
        else:
            self._fusion = None
        from collections import deque
        self._history = deque(maxlen=100)
        self.emotion_weight  = 0.4
        self.behavior_weight = 0.6

    def calculate(self, emotion_confidence: float, behavior_confidence: float) -> float:
        if self._fusion:
            score = self._fusion.get_confidence()
        else:
            score = np.clip(
                emotion_confidence * self.emotion_weight +
                behavior_confidence * self.behavior_weight,
                0.0, 1.0
            )
        self._history.append(score)
        return float(score)

    def get_average_confidence(self, n: int = 10) -> float:
        if not self._history:
            return 0.5
        return float(np.mean(list(self._history)[-n:]))

    def push_emotion_probs(self, probs: Dict[str, float]):
        """Call this after each frame to feed CNN probs into fusion engine."""
        if self._fusion:
            self._fusion.extractor.push_emotion(probs)
