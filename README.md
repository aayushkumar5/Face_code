# FaceCode V2 - Adaptive AI Coding Platform

**Real-time emotion-aware coding education platform that adapts to your learning style**

## 🎯 Project Overview

FaceCode is an intelligent coding platform that uses **facial emotion analysis** and **behavioral tracking** to create a personalized, adaptive learning experience. The system dynamically adjusts problem difficulty and provides intelligent hints based on your confidence level.

### Key Innovation
Unlike static coding platforms, FaceCode **observes you** while you code:
- 😊 Happy & confident? → Harder problems
- 😕 Confused & stuck? → Easier problems + hints
- ⏰ Taking too long? → Progressive guidance

## ✨ Features

### 1. Real-Time Emotion Detection
- Webcam-based facial expression analysis using DeepFace
- Detects 7 emotions: happy, neutral, sad, angry, surprise, fear, disgust
- Emotion smoothing over 10-frame buffer for stability

### 2. Multi-Signal Confidence Estimation
Combines three signals:
- **Emotion (40%)**: Facial expression confidence
- **Behavior (30%)**: Typing speed, activity patterns
- **Progress (30%)**: Error rate, test success

### 3. Adaptive Difficulty System
- **3 Levels**: Easy → Medium → Hard
- **Dynamic Adjustment**: Based on performance metrics
- **Smart Triggers**:
  - ⬆️ Increase: High confidence + quick solve + no hints
  - ⬇️ Decrease: Low confidence OR slow solve OR many hints

### 4. Progressive Hint System
Four hint levels per problem:
1. **Conceptual**: High-level problem-solving approach
2. **Algorithmic**: Algorithm structure and approach
3. **Implementation**: Code hints and snippets
4. **Solution**: Near-complete guidance

### 5. Secure Code Execution
- Subprocess isolation (not `exec()`)
- Timeout protection (5 seconds default)
- Syntax validation before execution
- Multiple test case validation

### 6. Session Persistence
- SQLite database stores all sessions
- Track progress over time
- Detailed analytics and statistics
- Emotion logs for research

## 📁 Project Structure

```
facecode_v2/
├── backend/
│   ├── emotion_engine.py      # Emotion detection + confidence calculation
│   ├── adaptive_engine.py     # Difficulty adjustment + hints
│   ├── problem_bank.py        # 15+ coding problems
│   └── code_executor.py       # Safe code execution
├── app.py                     # Main Streamlit application
├── database.py                # SQLite session tracking
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Webcam (optional but recommended)
- 4GB+ RAM

### Installation

```bash
# 1. Clone/download project
cd facecode_v2

# 2. Create virtual environment (recommended)
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# First run will download DeepFace models (~100MB)
# This may take 2-3 minutes
```

### Run the Application

```bash
streamlit run app.py
```

Application opens at: `http://localhost:8501`

### First Use

1. **Enable Camera**: Check "Enable Emotion Detection" in sidebar
2. **Get Problem**: Click "New Problem" to start
3. **Write Code**: Type your solution in the editor
4. **Run Tests**: Click "Run Code" to validate
5. **Submit**: Click "Submit" when all tests pass

## 🎓 How It Works

### System Pipeline

```
┌─────────────┐
│   Webcam    │
│   Stream    │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ Emotion Engine  │
│ - Face detect   │
│ - Emotion class │
└────────┬────────┘
         │
         ├──────────────┐
         │              │
         ▼              ▼
┌────────────┐   ┌──────────────┐
│ Behavior   │   │  Confidence  │
│ Tracker    │──▶│  Calculator  │
│ - Typing   │   │  (Weighted   │
│ - Errors   │   │   Combine)   │
└────────────┘   └──────┬───────┘
                        │
                        ▼
                 ┌──────────────┐
                 │  Adaptive    │
                 │  Engine      │
                 │ - Difficulty │
                 │ - Hints      │
                 └──────┬───────┘
                        │
                        ▼
                 ┌──────────────┐
                 │   Problem    │
                 │  Selection   │
                 └──────────────┘
```

### Confidence Formula

```python
overall_confidence = (
    emotion_score * 0.4 +      # From facial expression
    behavior_score * 0.6        # From activity + errors
)

behavior_score = (
    inactivity_score * 0.4 +
    typing_speed_score * 0.3 +
    error_rate_score * 0.3
)
```

### Difficulty Adjustment Logic

```python
# INCREASE difficulty if:
solved == True AND
avg_confidence > 0.75 AND
time < 240 seconds AND
hints_used == 0

# DECREASE difficulty if:
solved == False OR
avg_confidence < 0.35 OR
time > 600 seconds OR
hints_used > 2
```

## 📚 Problem Bank

### Easy (5 problems)
- Sum Two Numbers
- Check Even Number
- Find Maximum of Two
- String Length (without `len()`)
- Reverse String

### Medium (5 problems)
- Find Maximum in List
- Count Vowels
- Palindrome Checker
- Sum of List (without `sum()`)
- Remove Duplicates

### Hard (3 problems)
- Two Sum (Hash Map)
- Fibonacci Sequence
- Valid Parentheses (Stack)

**Total: 15+ problems** across different categories (basics, strings, arrays, recursion, stacks)

## 🔧 Technical Details

### Technologies Used
- **Frontend**: Streamlit (Python web framework)
- **Emotion Detection**: DeepFace + TensorFlow
- **Computer Vision**: OpenCV
- **Database**: SQLite
- **Code Execution**: Python subprocess

### Security Features
1. **Subprocess Isolation**: Code runs in separate process
2. **Timeout Protection**: 5-second execution limit
3. **Syntax Validation**: Pre-execution syntax checking
4. **No System Access**: Sandboxed environment

### Performance
- **Emotion Analysis**: ~1 frame per 1.5 seconds
- **Code Execution**: <1 second for simple problems
- **UI Responsiveness**: Real-time updates
- **Memory Usage**: ~500MB with models loaded

## 📊 Evaluation & Metrics

### Tracked Metrics

1. **Emotion Classification**
   - Face detection rate
   - Emotion prediction confidence
   - Smoothing effectiveness

2. **Problem Completion**
   - Problems solved vs attempted
   - Time to completion
   - Hints used per problem

3. **Frustration Reduction**
   - Time in confused state
   - Hint effectiveness
   - Recovery time after stuck

4. **Adaptive Success**
   - Difficulty change appropriateness
   - User satisfaction (completion rate)
   - Learning curve progression

### Database Schema

```sql
-- Sessions table
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    problem_id TEXT,
    difficulty TEXT,
    solved BOOLEAN,
    time_spent REAL,
    hints_used INTEGER,
    avg_confidence REAL,
    avg_emotion_confidence REAL,
    avg_behavior_confidence REAL,
    emotion_log TEXT,
    error_count INTEGER,
    success_count INTEGER
);

-- Confidence tracking
CREATE TABLE confidence_log (
    id INTEGER PRIMARY KEY,
    session_id INTEGER,
    timestamp TEXT,
    overall_confidence REAL,
    emotion_confidence REAL,
    behavior_confidence REAL,
    current_emotion TEXT
);

-- Difficulty changes
CREATE TABLE difficulty_changes (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    old_difficulty TEXT,
    new_difficulty TEXT,
    reason TEXT,
    session_id INTEGER
);
```

## 🎯 2-Week Implementation Timeline

### Week 1: Core Features
- **Day 1-2**: Setup + test all components independently
- **Day 3-4**: Secure code execution + database
- **Day 5-7**: Analytics dashboard + testing

### Week 2: Polish + Presentation
- **Day 8-9**: User testing + bug fixes
- **Day 10-11**: Documentation + video demo
- **Day 12-13**: Presentation prep + rehearsal
- **Day 14**: Buffer + final touches

## 🐛 Troubleshooting

### Camera Not Working
```bash
# Test camera access
python -c "import cv2; cap = cv2.VideoCapture(0); print('OK' if cap.isOpened() else 'FAIL')"

# Grant browser camera permissions
# Check no other app is using camera
```

### DeepFace Installation Issues
```bash
# Reinstall TensorFlow
pip install tensorflow==2.13.0 --force-reinstall

# Manual model download
python -c "from deepface import DeepFace; DeepFace.build_model('Emotion')"
```

### Import Errors
```bash
# Ensure you're in virtual environment
# Reinstall all dependencies
pip install -r requirements.txt --force-reinstall
```

### Database Locked
```bash
# Close all instances of the app
# Delete facecode_sessions.db and restart
```

## 🚀 Future Enhancements

- [ ] More programming languages (JavaScript, Java, C++)
- [ ] LLM-powered dynamic hint generation
- [ ] Voice tone analysis
- [ ] Collaborative coding mode
- [ ] Mobile app version
- [ ] Progress analytics dashboard
- [ ] Export sessions for research

## 📄 License

MIT License - Free for educational and research use.

## 🤝 Contributing

Pull requests welcome! Areas for improvement:
- Additional coding problems
- Better emotion detection models
- UI/UX enhancements
- Multi-language support

## 👨‍💻 Author

Built for CSE AI/ML Project
**Timeline**: 2 weeks
**Focus**: Adaptive learning + Emotion AI

## 📧 Support

For issues:
1. Check Troubleshooting section
2. Review error messages
3. Test components independently
4. Verify all dependencies installed

---

**Ready to start? Run `streamlit run app.py` and happy coding! 🎯💻**
