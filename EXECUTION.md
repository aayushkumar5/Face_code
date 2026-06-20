# Execution Guide

See [README.md](README.md) for prerequisites and installation.

Start the API from the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python api_server.py
```

Start the UI in another terminal:

```powershell
cd Frontend
npm run dev
```

The UI runs at `http://localhost:3000` and proxies `/api` and `/ws` requests to
the backend at `http://127.0.0.1:8000`.
