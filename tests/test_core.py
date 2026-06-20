import sys
import json
from pathlib import Path
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "engines"))
sys.path.insert(0, str(ROOT / "backend"))

from adaptive_engine import AdaptiveEngine
from code_executor import CodeExecutor
from database import FaceCodeDatabase
from auth import SessionSigner, SessionTokenError
from problem_bank import ProblemBank
from config import Settings
from confidence_fusion_engine import FusionMLP
from session_logger import SessionLogger


def test_code_executor_runs_expected_function():
    result = CodeExecutor().execute_code(
        "def add(a, b):\n    return a + b\n",
        [{"input": [2, 3], "expected": 5}],
    )
    assert result["all_passed"] is True
    assert result["test_results"][0]["actual"] == 5


def test_code_executor_allows_prints_without_corrupting_result():
    result = CodeExecutor().execute_code(
        "def add(a, b):\n    print('working')\n    return a + b\n",
        [{"input": [1, 4], "expected": 5}],
    )
    assert result["all_passed"] is True


def test_all_reference_solutions_pass_their_tests():
    executor = CodeExecutor()
    for problem in ProblemBank().problems.values():
        result = executor.execute_code(
            problem.solution,
            [
                {"input": test.input, "expected": test.expected}
                for test in problem.test_cases
            ],
        )
        assert result["all_passed"], f"{problem.id}: {result}"


def test_code_executor_rejects_unsafe_code():
    executor = CodeExecutor()
    imported = executor.execute_code(
        "import os\ndef solve():\n    return os.getcwd()\n",
        [{"input": [], "expected": ""}],
    )
    opened = executor.execute_code(
        "def solve():\n    return open('secret.txt').read()\n",
        [{"input": [], "expected": ""}],
    )
    assert imported["success"] is False
    assert "Imports are disabled" in imported["error"]
    assert opened["success"] is False
    assert "not allowed" in opened["error"]


def test_adaptive_engines_do_not_share_state():
    first = AdaptiveEngine()
    second = AdaptiveEngine()
    first.select_problem()
    first.get_next_hint()
    assert len(first.hints_provided) == 1
    assert second.hints_provided == []
    assert second.current_problem is None


def test_database_returns_emotion_breakdown(tmp_path):
    database = FaceCodeDatabase(str(tmp_path / "facecode.db"))
    database.save_session({
        "client_session_id": "session-a",
        "problem_id": "E001",
        "problem_title": "Add",
        "difficulty": "EASY",
        "category": "basics",
        "solved": True,
        "dominant_emotion": "happy",
    })
    stats = database.get_statistics()
    assert stats["total_sessions"] == 1
    assert stats["emotion_breakdown"] == {"happy": 1}


def test_database_scopes_analytics_to_session(tmp_path):
    database = FaceCodeDatabase(str(tmp_path / "facecode.db"))
    for session_id, emotion in (("session-a", "happy"), ("session-b", "sad")):
        database.save_session({
            "client_session_id": session_id,
            "problem_id": "E001",
            "solved": True,
            "dominant_emotion": emotion,
        })
    stats = database.get_statistics(client_session_id="session-a")
    assert stats["total_sessions"] == 1
    assert stats["total_solved"] == 1
    assert stats["emotion_breakdown"] == {"happy": 1}


def test_signed_session_rejects_mismatch_and_tampering():
    signer = SessionSigner("a-secure-test-secret-that-is-long-enough", 60)
    session_id, token, _ = signer.issue()
    assert signer.verify(token, session_id) == session_id

    try:
        signer.verify(token, "another-session")
        assert False, "mismatched session should be rejected"
    except SessionTokenError:
        pass

    try:
        signer.verify(token + "changed", session_id)
        assert False, "tampered token should be rejected"
    except SessionTokenError:
        pass


def test_database_deletes_only_requested_session(tmp_path):
    database = FaceCodeDatabase(str(tmp_path / "facecode.db"))
    for session_id in ("session-a", "session-b"):
        database.save_session({
            "client_session_id": session_id,
            "problem_id": "E001",
            "solved": True,
        })
    assert database.delete_client_session("session-a") == 1
    assert database.get_statistics("session-a")["total_sessions"] == 0
    assert database.get_statistics("session-b")["total_sessions"] == 1


def test_production_settings_fail_closed_without_runner(tmp_path, monkeypatch):
    for name in (
        "FACECODE_RUNNER_URL",
        "FACECODE_RUNNER_SECRET",
        "FACECODE_REQUIRE_SESSION_AUTH",
        "FACECODE_ALLOW_LOCAL_CODE_EXECUTION",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FACECODE_ENV", "production")
    monkeypatch.setenv("FACECODE_SECRET_KEY", "s" * 40)
    try:
        Settings.from_env(tmp_path)
        assert False, "production without an isolated runner should fail"
    except RuntimeError as exc:
        assert "FACECODE_RUNNER_URL" in str(exc)


def test_fusion_model_trains_saves_and_loads(tmp_path):
    log_path = tmp_path / "training.jsonl"
    samples = [
        {"features": [value] * 22, "outcome": value}
        for value in (0.1, 0.3, 0.7, 0.9)
    ]
    log_path.write_text(
        "".join(json.dumps(sample) + "\n" for sample in samples),
        encoding="utf-8",
    )
    model_path = tmp_path / "fusion.npz"
    model = FusionMLP()
    model.train_offline(str(log_path), epochs=2, save_path=str(model_path))
    loaded = FusionMLP()
    assert loaded.load(str(model_path)) is True
    assert 0 <= loaded.predict(np.zeros(22)) <= 1


def test_session_logger_reports_written_samples(tmp_path):
    log_path = tmp_path / "sessions.jsonl"
    logger = SessionLogger(str(log_path))
    logger.push_emotion({"happy": 0.8, "neutral": 0.2})
    assert logger.commit(solved=True, time_spent=60, hints_used=0) == 1
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 1
