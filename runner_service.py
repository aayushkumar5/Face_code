"""Internal-only service for running untrusted exercise submissions."""

import asyncio
import hmac
import os

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend.engines.code_executor import CodeExecutor


RUNNER_SECRET = os.getenv("FACECODE_RUNNER_SECRET", "")
if len(RUNNER_SECRET) < 32 or RUNNER_SECRET.startswith("replace-with-"):
    raise RuntimeError("FACECODE_RUNNER_SECRET must contain at least 32 characters")

app = FastAPI(title="FaceCode Isolated Runner", docs_url=None, redoc_url=None)
executor = CodeExecutor(timeout=int(os.getenv("FACECODE_RUNNER_TIMEOUT", "5")))
capacity = asyncio.Semaphore(int(os.getenv("FACECODE_RUNNER_CONCURRENCY", "2")))


class ExecutionRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50_000)
    test_cases: list[dict] = Field(min_length=1, max_length=20)


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/execute")
async def execute(
    request: ExecutionRequest,
    x_runner_secret: str = Header(default=""),
):
    if not hmac.compare_digest(x_runner_secret, RUNNER_SECRET):
        raise HTTPException(status_code=401, detail="Invalid runner credential")
    async with capacity:
        return await run_in_threadpool(
            executor.execute_code,
            request.code,
            request.test_cases,
        )
