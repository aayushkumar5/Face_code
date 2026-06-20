# FaceCode

FaceCode is an adaptive coding practice application. A React interface presents
Python exercises, streams webcam frames to a FastAPI backend, and shows a
confidence estimate derived from facial emotion probabilities and coding
behavior. Difficulty and progressive hints adapt independently for each browser
session.

## Stack

- React 18 and Vite
- FastAPI and SQLite
- OpenCV face detection
- TensorFlow/Keras FER-2013 emotion CNN
- Restricted subprocess-based Python exercise runner

The bundled CNN recognizes angry, disgust, fear, happy, sad, surprise, and
neutral. Its recorded best validation accuracy is 58.8%; emotion estimates are
therefore learning signals, not reliable assessments of a person.

## Requirements

- Python 3.10 or 3.11 (the TensorFlow runtime does not support Python 3.13)
- Node.js 22.12 or newer
- A webcam for emotion analysis (the coding lab works without one)

## Setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cd Frontend
npm install
```

Install `requirements-training.txt` instead when running the archived training
notebooks or retraining the CNN.

## Run

Backend, from the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python api_server.py
```

Frontend, in a second terminal:

```powershell
cd Frontend
npm run dev
```

Open `http://localhost:3000`. API documentation is available at
`http://127.0.0.1:8000/docs` and health at `/api/health`.

## Tests

```powershell
python -m pytest
cd Frontend
npm run build
```

## Project Layout

```text
api_server.py                 Canonical FastAPI application
backend/database.py           SQLite persistence and analytics
backend/engines/              Emotion, confidence, adaptive, and runner logic
Frontend/src/                 React application
model/                        Runtime CNN and training summary
archive/NoteBook/             Training notebooks and evaluation plots
tests/                        Backend unit tests
```

## Security

The local runner rejects imports and dangerous built-ins, uses isolated Python
flags, and enforces a timeout. This is defense in depth for local/demo use, not
a complete sandbox. An internet-facing deployment must execute submissions in
disposable, resource-limited containers or microVMs under an unprivileged user.

Configure allowed frontend origins with `FACECODE_CORS_ORIGINS` as a
comma-separated list. In-memory session state is appropriate for one backend
process; a scaled deployment should replace it with a shared session store.

## Production Deployment

The included Docker Compose stack separates submitted code from the API,
requires signed session credentials, scopes analytics to the active session,
adds request limits and security headers, and runs services without unnecessary
Linux capabilities. See [DEPLOYMENT.md](DEPLOYMENT.md) and `.env.example`.

Production mode refuses in-process code execution. The isolated runner must be
configured through `FACECODE_RUNNER_URL` and `FACECODE_RUNNER_SECRET`.
