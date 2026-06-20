"""
FaceCode V2 - FastAPI Backend
Production-ready REST API for FaceCode platform
"""

from fastapi import FastAPI, Header, HTTPException, WebSocket
from fastapi.responses import JSONResponse
from fastapi.websockets import WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from collections import deque
import sys
from pathlib import Path
import base64
import cv2
import numpy as np
import json
import time
import logging
import asyncio

# Add backend/engines to path so engine modules resolve correctly
project_root = Path(__file__).resolve().parent
backend_path = project_root / 'backend'
engines_path = backend_path / 'engines'
sys.path.insert(0, str(engines_path))
sys.path.insert(0, str(backend_path))

from emotion_engine_improved import EmotionEngine, BehaviorTracker, ConfidenceCalculator
from adaptive_engine import AdaptiveEngine
from code_executor import CodeExecutor
from remote_code_executor import RemoteCodeExecutor
from problem_bank import ProblemBank, DifficultyLevel
from database import FaceCodeDatabase
from auth import SessionSigner, SessionTokenError
from config import Settings
from middleware import ProductionGuardMiddleware, RateLimitMiddleware

settings = Settings.from_env(project_root)
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
session_signer = SessionSigner(settings.secret_key, settings.session_ttl_seconds)

# Initialize FastAPI app
app = FastAPI(
    title="FaceCode API",
    description="Adaptive AI Coding Platform with Emotion Analysis",
    version="2.1.0",
    docs_url=None if settings.production else "/docs",
    redoc_url=None if settings.production else "/redoc",
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.trusted_hosts))
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    ProductionGuardMiddleware,
    max_request_bytes=settings.max_request_bytes,
    production=settings.production,
)

# Shared stateless/heavyweight services
emotion_engine = EmotionEngine(
    cnn_model_path=str(project_root / "model" / "emotion_cnn.keras"),
    model_cache_dir=str(project_root / "model"),
)
code_executor = (
    RemoteCodeExecutor(settings.runner_url, settings.runner_secret)
    if settings.runner_url else CodeExecutor()
)
problem_bank = ProblemBank()
database = FaceCodeDatabase(str(settings.database_path))
emotion_inference_capacity = asyncio.Semaphore(1)

@dataclass
class SessionState:
    adaptive: AdaptiveEngine = field(default_factory=AdaptiveEngine)
    behavior: BehaviorTracker = field(default_factory=BehaviorTracker)
    confidence: ConfidenceCalculator = field(default_factory=ConfidenceCalculator)
    current_problem: object = None
    start_time: Optional[float] = None
    emotions: deque = field(default_factory=lambda: deque(maxlen=600))
    emotion_confidences: deque = field(default_factory=lambda: deque(maxlen=600))
    last_access: float = field(default_factory=time.time)


sessions: Dict[str, SessionState] = {}


def get_session(session_id: str) -> SessionState:
    if not session_id or len(session_id) > 128:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    now = time.time()
    stale = [
        key for key, value in sessions.items()
        if now - value.last_access > settings.session_ttl_seconds
    ]
    for key in stale:
        sessions.pop(key, None)
    if len(sessions) >= 1_000 and session_id not in sessions:
        oldest = min(sessions, key=lambda key: sessions[key].last_access)
        sessions.pop(oldest, None)
    state = sessions.setdefault(session_id, SessionState())
    state.last_access = now
    return state


def authorize_session(session_id: str, authorization: Optional[str]) -> None:
    if not settings.require_session_auth and not authorization:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing session credential")
    try:
        session_signer.verify(authorization[7:], session_id)
    except SessionTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

# ============================================================================
# PYDANTIC MODELS (Request/Response schemas)
# ============================================================================

class EmotionAnalysisRequest(BaseModel):
    image_base64: str = Field(min_length=4, max_length=3_000_000)
    session_id: str = Field(default="default", min_length=1, max_length=128)

class SessionCredentialResponse(BaseModel):
    session_id: str
    token: str
    expires_at: int

class EmotionAnalysisResponse(BaseModel):
    session_id: str
    face_detected: bool
    emotion: str
    emotion_confidence: float
    overall_confidence: float
    raw_emotions: Optional[Dict[str, float]]

class CodeExecutionRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50_000)
    problem_id: str = Field(min_length=1, max_length=32)
    session_id: str = Field(default="default", min_length=1, max_length=128)

class CodeExecutionResponse(BaseModel):
    success: bool
    all_passed: bool
    test_results: List[Dict]
    execution_time: float
    error: Optional[str]

class ProblemRequest(BaseModel):
    difficulty: Optional[str] = None
    session_id: str = Field(default="default", min_length=1, max_length=128)

class ProblemResponse(BaseModel):
    problem_id: str
    title: str
    description: str
    difficulty: str
    category: str
    starter_code: str
    test_cases: List[Dict]
    hints_available: int

class HintRequest(BaseModel):
    session_id: str = "default"

class ActivityRequest(BaseModel):
    session_id: str = Field(default="default", min_length=1, max_length=128)

class HintResponse(BaseModel):
    hint_available: bool
    hint_level: Optional[str]
    hint_text: Optional[str]
    hints_remaining: int

class SubmissionRequest(BaseModel):
    problem_id: str = Field(min_length=1, max_length=32)
    code: str = Field(min_length=1, max_length=50_000)
    session_id: str = Field(default="default", min_length=1, max_length=128)

class SubmissionResponse(BaseModel):
    solved: bool
    time_spent: float
    avg_confidence: float
    difficulty_change: Dict
    message: str

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "FaceCode API",
        "version": "2.1.0"
    }

@app.post("/api/sessions", response_model=SessionCredentialResponse)
async def create_session():
    session_id, token, expires_at = session_signer.issue()
    get_session(session_id)
    return SessionCredentialResponse(
        session_id=session_id,
        token=token,
        expires_at=expires_at,
    )

@app.get("/api/health")
async def health_check():
    """Detailed health check"""
    database_ready, runner_ready = await run_in_threadpool(
        lambda: (database.is_available(), code_executor.is_available())
    )
    runner_ready = runner_ready and bool(
        settings.runner_url or settings.allow_local_code_execution
    )
    healthy = database_ready and runner_ready and len(problem_bank.problems) > 0
    payload = {
        "status": "healthy" if healthy else "degraded",
        "components": {
            "emotion_engine": emotion_engine.backend,
            "database": database_ready,
            "problem_bank": len(problem_bank.problems) > 0,
            "code_runner": runner_ready,
        }
    }
    return JSONResponse(payload, status_code=200 if healthy else 503)

@app.post("/api/analyze-emotion", response_model=EmotionAnalysisResponse)
async def analyze_emotion(
    request: EmotionAnalysisRequest,
    authorization: Optional[str] = Header(default=None),
):
    """
    Analyze emotion from base64 image
    """
    try:
        # Decode base64 image
        authorize_session(request.session_id, authorization)
        state = get_session(request.session_id)
        img_data = base64.b64decode(request.image_base64, validate=True)
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            raise HTTPException(status_code=400, detail="Invalid image data")
        
        # Process frame
        async with emotion_inference_capacity:
            result = await run_in_threadpool(emotion_engine.process_frame, frame, False)
        if result['face_detected']:
            state.emotions.append(result['emotion'])
            state.emotion_confidences.append(result['emotion_confidence'])
        
        # Update behavior tracker
        if result.get('raw_probs'):
            state.confidence.push_emotion_probs(result['raw_probs'])
        behavior_conf = state.behavior.calculate_behavior_confidence()
        
        # Calculate overall confidence
        overall = state.confidence.calculate(
            result['emotion_confidence'],
            behavior_conf
        )
        
        return EmotionAnalysisResponse(
            session_id=request.session_id,
            face_detected=result['face_detected'],
            emotion=result['emotion'],
            emotion_confidence=result['emotion_confidence'],
            overall_confidence=overall,
            raw_emotions=result['raw_emotions']
        )
    
    except HTTPException:
        raise
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/get-problem", response_model=ProblemResponse)
async def get_problem(
    request: ProblemRequest,
    authorization: Optional[str] = Header(default=None),
):
    """
    Get a coding problem based on current difficulty
    """
    try:
        authorize_session(request.session_id, authorization)
        state = get_session(request.session_id)
        if request.difficulty:
            try:
                difficulty = DifficultyLevel[request.difficulty.upper()]
            except KeyError:
                raise HTTPException(status_code=400, detail="Unknown difficulty")
        else:
            difficulty = state.adaptive.current_difficulty
        
        # Select problem
        problem = state.adaptive.select_problem(difficulty)
        
        state.current_problem = problem
        state.start_time = time.time()
        
        # Reset behavior tracker
        state.behavior.reset()
        state.confidence.reset_problem()
        state.emotions.clear()
        state.emotion_confidences.clear()
        
        return ProblemResponse(
            problem_id=problem.id,
            title=problem.title,
            description=problem.description,
            difficulty=problem.difficulty.name,
            category=problem.category,
            starter_code=problem.starter_code,
            test_cases=[
                {
                    'input': tc.input,
                    'expected': tc.expected,
                    'description': tc.description
                }
                for tc in problem.test_cases[:2]
            ],
            hints_available=len(problem.hints)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/activity", status_code=204)
async def record_activity(
    request: ActivityRequest,
    authorization: Optional[str] = Header(default=None),
):
    """Record real editor activity for behavioral confidence."""
    authorize_session(request.session_id, authorization)
    state = get_session(request.session_id)
    state.behavior.record_activity()
    state.confidence.record_activity()

@app.post("/api/execute-code", response_model=CodeExecutionResponse)
async def execute_code(
    request: CodeExecutionRequest,
    authorization: Optional[str] = Header(default=None),
):
    """
    Execute user code against test cases
    """
    try:
        # Get problem
        authorize_session(request.session_id, authorization)
        if not settings.runner_url and not settings.allow_local_code_execution:
            raise HTTPException(
                status_code=503,
                detail="Code execution requires a configured isolated runner",
            )
        state = get_session(request.session_id)
        problem = state.current_problem
        
        if not problem:
            raise HTTPException(status_code=400, detail="No active problem")
        if problem.id != request.problem_id:
            raise HTTPException(status_code=409, detail="Problem does not match active session")
        
        # Execute code
        result = await run_in_threadpool(
            code_executor.execute_code,
            request.code,
            [
                {'input': tc.input, 'expected': tc.expected}
                for tc in problem.test_cases
            ],
        )
        
        # Update behavior tracker
        if result['all_passed']:
            state.behavior.record_success()
        else:
            state.behavior.record_error()
        state.confidence.record_run(result['all_passed'])
        
        return CodeExecutionResponse(
            success=result['success'],
            all_passed=result['all_passed'],
            test_results=result['test_results'],
            execution_time=result['execution_time'],
            error=result.get('error')
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/get-hint", response_model=HintResponse)
async def get_hint(
    request: HintRequest,
    authorization: Optional[str] = Header(default=None),
):
    """
    Get next progressive hint
    """
    try:
        authorize_session(request.session_id, authorization)
        state = get_session(request.session_id)
        hint = state.adaptive.get_next_hint()
        
        if hint:
            return HintResponse(
                hint_available=True,
                hint_level=hint['level'].name,
                hint_text=hint['text'],
                hints_remaining=len(state.adaptive.current_problem.hints) - hint['index']
            )
        else:
            return HintResponse(
                hint_available=False,
                hint_level=None,
                hint_text=None,
                hints_remaining=0
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/submit-solution", response_model=SubmissionResponse)
async def submit_solution(
    request: SubmissionRequest,
    authorization: Optional[str] = Header(default=None),
):
    """
    Submit solution and adjust difficulty
    """
    try:
        # Get session data
        authorize_session(request.session_id, authorization)
        if not settings.runner_url and not settings.allow_local_code_execution:
            raise HTTPException(
                status_code=503,
                detail="Code execution requires a configured isolated runner",
            )
        state = get_session(request.session_id)
        problem = state.current_problem
        start_time = state.start_time
        
        if not problem or not start_time:
            raise HTTPException(status_code=400, detail="No active problem")
        if problem.id != request.problem_id:
            raise HTTPException(status_code=409, detail="Problem does not match active session")
        
        # Execute code to verify
        result = await run_in_threadpool(
            code_executor.execute_code,
            request.code,
            [
                {'input': tc.input, 'expected': tc.expected}
                for tc in problem.test_cases
            ],
        )
        
        if not result['all_passed']:
            raise HTTPException(status_code=400, detail="Not all tests passed")
        
        # Calculate metrics
        time_spent = time.time() - start_time
        avg_confidence = state.confidence.get_average_confidence()
        
        # Adjust difficulty
        adjustment = state.adaptive.adjust_difficulty(
            avg_confidence,
            time_spent,
            True
        )
        
        # Save to database
        session_data = {
            'client_session_id': request.session_id,
            'problem_id': problem.id,
            'problem_title': problem.title,
            'difficulty': problem.difficulty.name,
            'category': problem.category,
            'solved': True,
            'time_spent': time_spent,
            'hints_used': len(state.adaptive.hints_provided),
            'avg_confidence': avg_confidence,
            'avg_emotion_confidence': (
                sum(state.emotion_confidences) / len(state.emotion_confidences)
                if state.emotion_confidences else 0.5
            ),
            'dominant_emotion': (
                max(set(state.emotions), key=state.emotions.count)
                if state.emotions else 'unknown'
            ),
            'avg_behavior_confidence': state.behavior.calculate_behavior_confidence(),
            'emotion_log': [],
            'error_count': state.behavior.error_count,
            'success_count': state.behavior.success_count
        }
        
        session_id = database.save_session(session_data)
        database.save_difficulty_change(adjustment, session_id)
        
        # Record attempt
        state.adaptive.record_problem_attempt(True, time_spent, avg_confidence)
        state.start_time = None
        
        return SubmissionResponse(
            solved=True,
            time_spent=time_spent,
            avg_confidence=avg_confidence,
            difficulty_change=adjustment,
            message="Problem solved successfully!"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/session-stats")
async def get_session_stats(
    session_id: str = "default",
    authorization: Optional[str] = Header(default=None),
):
    """
    Get current session statistics
    """
    try:
        authorize_session(session_id, authorization)
        summary = get_session(session_id).adaptive.get_session_summary()
        return {
            "session_id": session_id,
            "stats": summary
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/problems")
async def list_problems(difficulty: Optional[str] = None):
    """
    List available problems
    """
    try:
        if difficulty:
            try:
                diff_level = DifficultyLevel[difficulty.upper()]
            except KeyError:
                raise HTTPException(status_code=400, detail="Unknown difficulty")
            problems = problem_bank.get_problems_by_difficulty(diff_level)
        else:
            problems = list(problem_bank.problems.values())
        
        return {
            "count": len(problems),
            "problems": [
                {
                    "id": p.id,
                    "title": p.title,
                    "difficulty": p.difficulty.name,
                    "category": p.category
                }
                for p in problems
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics")
async def get_analytics(
    session_id: str,
    authorization: Optional[str] = Header(default=None),
):
    """
    Get overall analytics
    """
    try:
        authorize_session(session_id, authorization)
        stats = database.get_statistics(client_session_id=session_id)
        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/session-data", status_code=204)
async def delete_session_data(
    session_id: str,
    authorization: Optional[str] = Header(default=None),
):
    authorize_session(session_id, authorization)
    await run_in_threadpool(database.delete_client_session, session_id)
    sessions.pop(session_id, None)

# ============================================================================
# WEBSOCKET for Real-time Updates
# ============================================================================

@app.websocket("/ws/emotion-stream")
async def websocket_emotion_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time emotion streaming.
    Handles client disconnect cleanly without crashing the handler.
    """
    session_id = websocket.query_params.get("session_id", "default")
    token = websocket.query_params.get("token")
    if settings.require_session_auth or token:
        try:
            session_signer.verify(token or "", session_id)
        except SessionTokenError:
            await websocket.close(code=1008)
            return
    await websocket.accept()
    state = get_session(session_id)
    last_frame_at = 0.0

    try:
        while True:
            # Receive image data — raises WebSocketDisconnect when client leaves
            data = await websocket.receive_text()
            if settings.require_session_auth or token:
                try:
                    session_signer.verify(token or "", session_id)
                except SessionTokenError:
                    await websocket.close(code=1008)
                    return
            state.last_access = time.time()

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                continue   # ignore malformed messages, keep connection alive

            if message.get('type') == 'frame' and message.get('image'):
                try:
                    now = time.monotonic()
                    if now - last_frame_at < 0.5:
                        continue
                    last_frame_at = now
                    if len(message['image']) > 3_000_000:
                        await websocket.close(code=1009)
                        return
                    img_data = base64.b64decode(message['image'], validate=True)
                    nparr = np.frombuffer(img_data, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    if frame is None:
                        continue   # skip undecodable frames silently

                    async with emotion_inference_capacity:
                        result = await run_in_threadpool(
                            emotion_engine.process_frame, frame, False
                        )
                    if result['face_detected']:
                        state.emotions.append(result['emotion'])
                        state.emotion_confidences.append(result['emotion_confidence'])
                    if result.get('raw_probs'):
                        state.confidence.push_emotion_probs(result['raw_probs'])
                    overall = state.confidence.calculate(
                        result['emotion_confidence'],
                        state.behavior.calculate_behavior_confidence()
                    )

                    await websocket.send_json({
                        'type': 'emotion_result',
                        'data': {
                            'emotion': result['emotion'],
                            'confidence': overall,
                            'emotion_confidence': result['emotion_confidence'],
                            'face_detected': result['face_detected']
                        }
                    })
                except Exception:
                    # Frame processing error — skip this frame, keep connection alive
                    continue

    except WebSocketDisconnect:
        # Normal — client navigated away or closed the tab
        pass
    except Exception:
        # Unexpected error — close gracefully
        try:
            await websocket.close(code=1011)
        except Exception:
            pass

# ============================================================================
# STARTUP/SHUTDOWN EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    purged = await run_in_threadpool(
        database.purge_expired_sessions,
        settings.retention_days,
    )
    print("🚀 FaceCode API Starting...")
    print(f"   - Emotion Engine: {'✅' if emotion_engine.deepface_available else '⚠️'}")
    print(f"   - Problems Loaded: {len(problem_bank.problems)}")
    print(f"   - Expired Sessions Purged: {purged}")
    print("✅ FaceCode API Ready!")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    database.close()
    print("👋 FaceCode API Shutdown")

# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_server:app",
        host="127.0.0.1",   # explicit IPv4 — avoids Windows IPv6 mismatch
        port=8000,
        reload=False,        # reload=True causes double-init bugs on Windows
        log_level="info",
        ws_max_size=settings.max_request_bytes,
    )
