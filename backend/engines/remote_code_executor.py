"""Client for the isolated FaceCode runner service."""

from typing import Dict, List

import httpx


class RemoteCodeExecutor:
    def __init__(self, base_url: str, secret: str, timeout: float = 35.0):
        self.base_url = base_url.rstrip("/")
        self.secret = secret
        self.timeout = timeout

    def execute_code(self, code: str, test_cases: List[Dict]) -> Dict:
        try:
            response = httpx.post(
                f"{self.base_url}/execute",
                json={"code": code, "test_cases": test_cases},
                headers={"X-Runner-Secret": self.secret},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            return {
                "success": False,
                "all_passed": False,
                "test_results": [],
                "execution_time": 0.0,
                "error": f"Isolated runner unavailable: {exc}",
            }

    def validate_syntax(self, code: str):
        # Validation is repeated inside the trusted runner.
        return True, ""

    def is_available(self) -> bool:
        try:
            response = httpx.get(
                f"{self.base_url}/health",
                headers={"X-Runner-Secret": self.secret},
                timeout=2.0,
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False
