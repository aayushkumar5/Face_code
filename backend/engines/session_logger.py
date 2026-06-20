"""Collect confidence feature snapshots for offline fusion-model training."""

import json
import os
import time

try:
    from .confidence_fusion_engine import SignalExtractor
except ImportError:  # Direct script execution
    from confidence_fusion_engine import SignalExtractor


class SessionLogger:
    def __init__(self, log_path: str = "data/session_log.jsonl"):
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        self._extractor = SignalExtractor()
        self._session_features = []

    def push_emotion(self, probabilities: dict) -> None:
        self._extractor.push_emotion(probabilities)
        self._session_features.append(self._extractor.extract().tolist())

    def record_keystroke(self) -> None:
        self._extractor.record_keystroke()

    def record_run(self, passed: bool) -> None:
        self._extractor.record_run(passed)

    def commit(self, solved: bool, time_spent: float, hints_used: int) -> int:
        """Append labeled snapshots and return the number written."""
        if not self._session_features:
            return 0

        if not solved:
            outcome = 0.1
        elif hints_used == 0 and time_spent < 240:
            outcome = 1.0
        elif hints_used <= 1:
            outcome = 0.7
        else:
            outcome = 0.5

        sample_count = len(self._session_features)
        timestamp = time.time()
        with open(self.log_path, "a", encoding="utf-8") as log_file:
            for features in self._session_features:
                record = {
                    "features": features,
                    "outcome": outcome,
                    "ts": timestamp,
                }
                log_file.write(json.dumps(record, separators=(",", ":")) + "\n")

        self.reset()
        return sample_count

    def reset(self) -> None:
        self._session_features.clear()
        self._extractor.reset_behavior()
