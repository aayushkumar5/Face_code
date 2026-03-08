"""
FaceCode V2 - FastAPI Backend
Production-ready REST API for FaceCode platform
"""

from fastapi import FastAPI, HTTPException, File, UploadFile, WebSocket
from fastapi.websockets import WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import sys
from pathlib import Path
import base64
import cv2
import numpy as np
import json

# Add backend to path
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

from backend.emotion_engine_improved import EmotionEngine, BehaviorTracker, ConfidenceCalculator
from backend.adaptive_engine import AdaptiveEngine
from backend.code_executor import CodeExecutor
from backend.problem_bank import ProblemBank, DifficultyLevel
from database import FaceCodeDatabase

# Initialize FastAPI app
app = FastAPI(
    title="FaceCode API",
    description="Adaptive AI Coding Platform with Emotion Analysis",
    version="2.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances (in production, use dependency injection)
emotion_engine = EmotionEngine()
behavior_tracker = BehaviorTracker()
confidence_calc = ConfidenceCalculator()
adaptive_engine = AdaptiveEngine()
code_executor = CodeExecutor()
problem_bank = ProblemBank()
database = FaceCodeDatabase()

# Session storage (in production, use Redis or database)
sessions = {}

# ============================================================================
# PYDANTIC MODELS (Request/Response schemas)
# ============================================================================

class EmotionAnalysisRequest(BaseModel):
    image_base64: str
    session_id: Optional[str] = "default"

class EmotionAnalysisResponse(BaseModel):
    session_id: str
    face_detected: bool
    emotion: str
    emotion_confidence: float
    overall_confidence: float
    raw_emotions: Optional[Dict[str, float]]

class CodeExecutionRequest(BaseModel):
    code: str
    problem_id: str
    session_id: Optional[str] = "default"

class CodeExecutionResponse(BaseModel):
    success: bool
    all_passed: bool
    test_results: List[Dict]
    execution_time: float
    error: Optional[str]

class ProblemRequest(BaseModel):
    difficulty: Optional[str] = None
    session_id: Optional[str] = "default"

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

class HintResponse(BaseModel):
    hint_available: bool
    hint_level: Optional[str]
    hint_text: Optional[str]
    hints_remaining: int

class SubmissionRequest(BaseModel):
    problem_id: str
    code: str
    session_id: str = "default"

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
        "version": "2.0.0"
    }

@app.get("/api/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "components": {
            "emotion_engine": emotion_engine.deepface_available,
            "database": True,
            "problem_bank": len(problem_bank.problems) > 0
        }
    }

@app.post("/api/analyze-emotion", response_model=EmotionAnalysisResponse)
async def analyze_emotion(request: EmotionAnalysisRequest):
    """
    Analyze emotion from base64 image
    """
    try:
        # Decode base64 image
        img_data = base64.b64decode(request.image_base64)
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            raise HTTPException(status_code=400, detail="Invalid image data")
        
        # Process frame
        result = emotion_engine.process_frame(frame)
        
        # Update behavior tracker
        behavior_tracker.record_activity()
        behavior_conf = behavior_tracker.calculate_behavior_confidence()
        
        # Calculate overall confidence
        overall = confidence_calc.calculate(
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
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/get-problem", response_model=ProblemResponse)
async def get_problem(request: ProblemRequest):
    """
    Get a coding problem based on current difficulty
    """
    try:
        # Get difficulty
        if request.difficulty:
            difficulty = DifficultyLevel[request.difficulty.upper()]
        else:
            difficulty = adaptive_engine.current_difficulty
        
        # Select problem
        problem = adaptive_engine.select_problem(difficulty)
        
        # Store in session
        if request.session_id not in sessions:
            sessions[request.session_id] = {}
        
        sessions[request.session_id]['current_problem'] = problem
        sessions[request.session_id]['start_time'] = __import__('time').time()
        
        # Reset behavior tracker
        behavior_tracker.reset()
        
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
                for tc in problem.test_cases
            ],
            hints_available=len(problem.hints)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/execute-code", response_model=CodeExecutionResponse)
async def execute_code(request: CodeExecutionRequest):
    """
    Execute user code against test cases
    """
    try:
        # Get problem
        session = sessions.get(request.session_id, {})
        problem = session.get('current_problem')
        
        if not problem:
            raise HTTPException(status_code=400, detail="No active problem")
        
        # Execute code
        result = code_executor.execute_code(
            request.code,
            [
                {'input': tc.input, 'expected': tc.expected}
                for tc in problem.test_cases
            ]
        )
        
        # Update behavior tracker
        if result['all_passed']:
            behavior_tracker.record_success()
        else:
            behavior_tracker.record_error()
        
        return CodeExecutionResponse(
            success=result['success'],
            all_passed=result['all_passed'],
            test_results=result['test_results'],
            execution_time=result['execution_time'],
            error=result.get('error')
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/get-hint", response_model=HintResponse)
async def get_hint(request: HintRequest):
    """
    Get next progressive hint
    """
    try:
        hint = adaptive_engine.get_next_hint()
        
        if hint:
            return HintResponse(
                hint_available=True,
                hint_level=hint['level'].name,
                hint_text=hint['text'],
                hints_remaining=len(adaptive_engine.current_problem.hints) - hint['index']
            )
        else:
            return HintResponse(
                hint_available=False,
                hint_level=None,
                hint_text=None,
                hints_remaining=0
            )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/submit-solution", response_model=SubmissionResponse)
async def submit_solution(request: SubmissionRequest):
    """
    Submit solution and adjust difficulty
    """
    try:
        # Get session data
        session = sessions.get(request.session_id, {})
        problem = session.get('current_problem')
        start_time = session.get('start_time')
        
        if not problem or not start_time:
            raise HTTPException(status_code=400, detail="No active problem")
        
        # Execute code to verify
        result = code_executor.execute_code(
            request.code,
            [
                {'input': tc.input, 'expected': tc.expected}
                for tc in problem.test_cases
            ]
        )
        
        if not result['all_passed']:
            raise HTTPException(status_code=400, detail="Not all tests passed")
        
        # Calculate metrics
        time_spent = __import__('time').time() - start_time
        avg_confidence = confidence_calc.get_average_confidence()
        
        # Adjust difficulty
        adjustment = adaptive_engine.adjust_difficulty(
            avg_confidence,
            time_spent,
            True
        )
        
        # Save to database
        session_data = {
            'problem_id': problem.id,
            'problem_title': problem.title,
            'difficulty': problem.difficulty.name,
            'category': problem.category,
            'solved': True,
            'time_spent': time_spent,
            'hints_used': len(adaptive_engine.hints_provided),
            'avg_confidence': avg_confidence,
            'avg_emotion_confidence': 0.7,  # Would come from session tracking
            'avg_behavior_confidence': behavior_tracker.calculate_behavior_confidence(),
            'emotion_log': [],
            'error_count': behavior_tracker.error_count,
            'success_count': behavior_tracker.success_count
        }
        
        session_id = database.save_session(session_data)
        database.save_difficulty_change(adjustment, session_id)
        
        # Record attempt
        adaptive_engine.record_problem_attempt(True, time_spent, avg_confidence)
        
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
async def get_session_stats(session_id: str = "default"):
    """
    Get current session statistics
    """
    try:
        summary = adaptive_engine.get_session_summary()
        return {
            "session_id": session_id,
            "stats": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/problems")
async def list_problems(difficulty: Optional[str] = None):
    """
    List available problems
    """
    try:
        if difficulty:
            diff_level = DifficultyLevel[difficulty.upper()]
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics")
async def get_analytics():
    """
    Get overall analytics
    """
    try:
        stats = database.get_statistics()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# WEBSOCKET for Real-time Updates
# ============================================================================

@app.websocket("/ws/emotion-stream")
async def websocket_emotion_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time emotion streaming.
    Handles client disconnect cleanly without crashing the handler.
    """
    await websocket.accept()

    try:
        while True:
            # Receive image data — raises WebSocketDisconnect when client leaves
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                continue   # ignore malformed messages, keep connection alive

            if message.get('type') == 'frame' and message.get('image'):
                try:
                    img_data = base64.b64decode(message['image'])
                    nparr = np.frombuffer(img_data, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    if frame is None:
                        continue   # skip undecodable frames silently

                    result = emotion_engine.process_frame(frame)

                    await websocket.send_json({
                        'type': 'emotion_result',
                        'data': {
                            'emotion': result['emotion'],
                            'confidence': result['emotion_confidence'],
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
    print("🚀 FaceCode API Starting...")
    print(f"   - Emotion Engine: {'✅' if emotion_engine.deepface_available else '⚠️'}")
    print(f"   - Problems Loaded: {len(problem_bank.problems)}")
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
        log_level="info"
    )
