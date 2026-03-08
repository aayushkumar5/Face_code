"""
FaceCode - Session Logger
Logs feature vectors + outcomes to train the Fusion MLP offline.
Attach this to your API server to collect real training data over time.
"""

import json
import os
import time
import numpy as np
from typing import Optional

try:
    from confidence_fusion_engine import SignalExtractor
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


class SessionLogger:
    """
    Records (feature_vector, outcome) pairs to a JSON-lines file.
    The file can later be fed to FusionMLP.train_offline().

    Attach to api_server.py:
        logger = SessionLogger("data/session_log.jsonl")
        # after each frame:
        logger.push_emotion(raw_probs)
        logger.record_keystroke()
        # at problem end:
        logger.commit(solved=True, time_spent=180, hints_used=0)
    """

    def __init__(self, log_path: str = "data/session_log.jsonl"):
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        self._extractor = SignalExtractor() if _AVAILABLE else None
        self._session_features = []

    # ── Delegate to extractor ──────────────────────────────

    def push_emotion(self, probs: dict):
        if self._extractor:
            self._extractor.push_emotion(probs)
            self._session_features.append(self._extractor.extract().tolist())

    def record_keystroke(self):
        if self._extractor:
            self._extractor.record_keystroke()

    def record_run(self, passed: bool):
        if self._extractor:
            self._extractor.record_run(passed)

    # ── Commit session ─────────────────────────────────────

    def commit(self, solved: bool, time_spent: float, hints_used: int):
        """
        Compute outcome score and write all logged feature snapshots to disk.

        Outcome scoring:
          solved + fast + no hints = 1.0
          solved + hints           = 0.6
          solved + slow            = 0.5
          not solved               = 0.1
        """
        if not self._session_features:
            return

        if solved:
            if hints_used == 0 and time_spent < 240:
                outcome = 1.0
            elif hints_used <= 1:
                outcome = 0.7
            else:
                outcome = 0.5
        else:
            outcome = 0.1

        with open(self.log_path, "a") as f:
            for feats in self._session_features:
                record = {"features": feats, "outcome": outcome,
                          "ts": time.time()}
                f.write(json.dumps(record) + "\n")

        self._reset()
        print(f"📝 Session logged ({len(self._session_features)} samples, outcome={outcome:.1f})")

    def _reset(self):
        self._session_features = []
        if self._extractor:
            self._extractor.reset_behavior()


# ─────────────────────────────────────────────────────────────
# Integration snippet for api_server.py
# ─────────────────────────────────────────────────────────────

INTEGRATION_GUIDE = """
# ── How to integrate SessionLogger in api_server.py ────────────────

from session_logger import SessionLogger
session_logger = SessionLogger("data/session_log.jsonl")

# In analyze_emotion endpoint, after processing frame:
if result["raw_probs"]:
    session_logger.push_emotion(result["raw_probs"])

# In execute_code endpoint, after each run:
session_logger.record_run(passed=result["all_passed"])

# In submit_solution endpoint, on success:
session_logger.commit(
    solved=True,
    time_spent=time_spent,
    hints_used=len(adaptive_engine.hints_provided)
)

# ── Training the Fusion MLP (run once you have enough data) ──────────
# python confidence_fusion_engine.py --train-fusion data/session_log.jsonl
"""

if __name__ == "__main__":
    print(INTEGRATION_GUIDE)
