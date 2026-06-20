"""Restricted Python function runner used by FaceCode exercises.

This reduces accidental and obvious abuse, but it is not an OS security
boundary. Public deployments should run submissions in disposable containers.
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple


class CodeExecutor:
    _BLOCKED_CALLS = {
        "__import__", "breakpoint", "compile", "eval", "exec", "globals",
        "delattr", "getattr", "help", "input", "locals", "open", "setattr",
        "vars",
    }
    _RESULT_MARKER = "__FACECODE_RESULT__"

    def __init__(self, timeout: int = 5, max_memory_mb: int = 128):
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        self.max_code_bytes = 50_000

    def _validate_code(self, code: str) -> Tuple[bool, str, Optional[str]]:
        if len(code.encode("utf-8")) > self.max_code_bytes:
            return False, "Code exceeds the 50 KB limit", None
        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as exc:
            return False, f"Syntax Error on line {exc.lineno}: {exc.msg}", None

        functions = [
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        ]
        if not functions:
            return False, "Define at least one public function", None

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                return False, "Imports are disabled in submitted code", None
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in self._BLOCKED_CALLS:
                    return False, f"Call to '{node.func.id}' is not allowed", None
            if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                return False, "Dunder attribute access is not allowed", None

        return True, "", functions[0]

    def execute_code(self, code: str, test_cases: List[Dict]) -> Dict[str, Any]:
        results = {
            "success": False,
            "test_results": [],
            "all_passed": False,
            "execution_time": 0.0,
            "error": None,
        }
        started = time.monotonic()
        valid, error, function_name = self._validate_code(code)
        if not valid:
            results["error"] = error
            return results

        runner = f'''import contextlib
import json
import sys

{code}

class _DiscardOutput:
    def write(self, value):
        return len(value)

    def flush(self):
        pass

if __name__ == "__main__":
    test_input = json.loads(sys.stdin.read())
    with contextlib.redirect_stdout(_DiscardOutput()), contextlib.redirect_stderr(_DiscardOutput()):
        result = globals()[{function_name!r}](*test_input)
    serialized = json.dumps(result)
    if len(serialized.encode("utf-8")) > 1_000_000:
        raise ValueError("Result exceeds the 1 MB limit")
    print({self._RESULT_MARKER!r} + serialized)
'''

        try:
            with tempfile.TemporaryDirectory(prefix="facecode_") as work_dir:
                script_path = os.path.join(work_dir, "submission.py")
                with open(script_path, "w", encoding="utf-8") as script:
                    script.write(runner)

                for test_case in test_cases:
                    test_result = self._run_single_test(script_path, test_case, work_dir)
                    results["test_results"].append(test_result)

            results["success"] = True
            results["all_passed"] = bool(test_cases) and all(
                item["passed"] for item in results["test_results"]
            )
        except Exception as exc:
            results["error"] = str(exc)
        finally:
            results["execution_time"] = time.monotonic() - started
        return results

    def _run_single_test(self, script_path: str, test_case: Dict, work_dir: str) -> Dict:
        result = {
            "input": test_case["input"],
            "expected": test_case["expected"],
            "actual": None,
            "passed": False,
            "error": None,
            "timeout": False,
        }
        try:
            process = subprocess.run(
                [sys.executable, "-I", "-S", script_path],
                input=json.dumps(test_case["input"]),
                capture_output=True,
                timeout=self.timeout,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=work_dir,
                env={"PYTHONIOENCODING": "utf-8"},
            )
            if process.returncode != 0:
                result["error"] = process.stderr.strip()[-2_000:]
                return result

            lines = [
                line for line in process.stdout.splitlines()
                if line.startswith(self._RESULT_MARKER)
            ]
            if not lines:
                result["error"] = "Function did not return a JSON-serializable result"
                return result
            actual = json.loads(lines[-1][len(self._RESULT_MARKER):])
            result["actual"] = actual
            result["passed"] = actual == test_case["expected"]
        except subprocess.TimeoutExpired:
            result["timeout"] = True
            result["error"] = f"Execution timed out after {self.timeout} seconds"
        except Exception as exc:
            result["error"] = str(exc)
        return result

    def validate_syntax(self, code: str) -> Tuple[bool, str]:
        valid, error, _ = self._validate_code(code)
        return valid, error

    def is_available(self) -> bool:
        return True
