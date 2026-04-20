"""
Code execution engine.

Runs user-submitted Python code in an isolated subprocess, validates it
against predefined test cases, and profiles its time complexity using the
`big_o` library.
"""

import subprocess
import tempfile
import json
import os
import sys
from typing import Dict, Optional, Tuple

# The runner template injects user code at this line offset.  When we
# report error line-numbers back to the frontend we subtract this value
# so the line number corresponds to what the student actually typed.
_USER_CODE_LINE_OFFSET = 15

# ── Per-problem test definitions ─────────────────────────────────────
# Each entry maps a problem ID to (function_name, test_case_code_block).
# The test-case block is injected verbatim into the runner template.

_PROBLEM_TESTS: Dict[str, Tuple[str, str]] = {
    "1": (
        "find_max",
        """
        if 'find_max' not in globals():
            return {"status": "Error", "message": "Function 'find_max' not defined."}
        test_cases = [
            ([1, 5, 3, 9, 2], 9),
            ([-5, -1, -10], -1),
            ([42], 42),
            ([0, 0, 0], 0),
            (list(range(100)), 99)
        ]""",
    ),
    "2": (
        "calculate_average",
        """
        if 'calculate_average' not in globals():
            return {"status": "Error", "message": "Function 'calculate_average' not defined."}
        test_cases = [
            ([10, 20, 30], 20.0),
            ([5, 5, 5, 5], 5.0),
            ([100], 100.0)
        ]""",
    ),
}


# ── Runner template ──────────────────────────────────────────────────
# Executed inside a subprocess.  Placeholders are replaced at runtime.

_RUNNER_TEMPLATE = """\
import sys
import json
import time
import traceback
import typing
from typing import *

try:
    import big_o
except ImportError:
    print(json.dumps({{"status": "Error", "message": "big_o library not found"}}))
    sys.exit(0)

# User Code
{user_code}

def run_tests():
    try:
        {test_cases}

        results = []
        all_passed = True

        for i, (args, expected) in enumerate(test_cases):
            try:
                if isinstance(args, tuple):
                    result = {func_name}(*args)
                else:
                    result = {func_name}(args)

                passed = (result == expected)
                if not passed:
                    all_passed = False

                results.append({{
                    "test_num": i + 1,
                    "input": str(args),
                    "expected": str(expected),
                    "actual": str(result),
                    "passed": passed
                }})
            except Exception as e:
                all_passed = False
                results.append({{
                    "test_num": i + 1,
                    "input": str(args),
                    "expected": str(expected),
                    "actual": f"Exception: {{str(e)}}",
                    "passed": False
                }})

        status = "Passed" if all_passed else "Failed"
        msg = "All tests passed!" if all_passed else "Some tests failed."
        return {{"status": status, "message": msg, "test_results": results}}
    except Exception as e:
        tb_str = traceback.format_exc()
        error_line = None
        for line in reversed(tb_str.splitlines()):
            if "File " in line and ", line " in line:
                try:
                    line_num_str = line.split(", line ")[1].split(",")[0]
                    error_line = int(line_num_str) - {line_offset}
                    if error_line < 1:
                        error_line = None
                    break
                except Exception:
                    pass
        return {{"status": "Error", "message": str(e), "traceback": tb_str, "error_line": error_line}}

def profile():
    try:
        def generator(n):
            return big_o.datagen.integers(n, -10000, 10000)

        best, others = big_o.big_o({func_name}, generator, n_repeats=10, min_n=100, max_n=10000)

        complexity_name = best.__class__.__name__
        big_o_map = {{
            "Constant": "O(1)",
            "Linear": "O(N)",
            "Quadratic": "O(N^2)",
            "Cubic": "O(N^3)",
            "Polynomial": "O(N^k)",
            "Logarithmic": "O(log N)",
            "Linearithmic": "O(N log N)",
            "Exponential": "O(2^N)"
        }}

        return {{
            "status": "Accepted",
            "time_complexity": str(best),
            "complexity_class": complexity_name,
            "big_o_notation": big_o_map.get(complexity_name, f"O({{complexity_name}})")
        }}
    except Exception as e:
        return {{"status": "Error", "message": f"Profiling failed: {{str(e)}}"}}

if __name__ == "__main__":
    test_result = run_tests()
    if test_result["status"] != "Passed":
        print(json.dumps(test_result))
    else:
        profile_result = profile()
        print(json.dumps(profile_result))
"""

_EXECUTION_TIMEOUT_SECONDS = 5


def _extract_error_line(stderr: str) -> Optional[int]:
    """Parse a Python traceback to find the offending line in user code."""
    for line in reversed(stderr.splitlines()):
        if "File " in line and ", line " in line:
            try:
                raw = line.split(", line ")[1].split(",")[0].strip()
                adjusted = int(raw) - _USER_CODE_LINE_OFFSET
                return adjusted if adjusted >= 1 else None
            except (ValueError, IndexError):
                pass
    return None


def run_and_profile_code(user_code: str, problem_id: str = "1") -> dict:
    """
    Execute *user_code* against test cases for *problem_id* and, if all
    tests pass, profile its time complexity.

    Returns a dict suitable for JSON-serialising to the frontend.
    """
    if problem_id not in _PROBLEM_TESTS:
        return {"status": "Error", "message": f"No test cases for problem {problem_id}"}

    func_name, test_block = _PROBLEM_TESTS[problem_id]

    runner_code = _RUNNER_TEMPLATE.format(
        user_code=user_code,
        func_name=func_name,
        test_cases=test_block,
        line_offset=_USER_CODE_LINE_OFFSET,
    )

    # Use the same Python interpreter that is running this server — no
    # hardcoded paths, works in any virtualenv.
    python = sys.executable

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(runner_code)
        temp_path = f.name

    try:
        result = subprocess.run(
            [python, temp_path],
            capture_output=True,
            text=True,
            timeout=_EXECUTION_TIMEOUT_SECONDS,
        )

        if result.stderr:
            return {
                "status": "Error",
                "message": result.stderr,
                "error_line": _extract_error_line(result.stderr),
            }

        output = result.stdout.strip()
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"status": "Error", "message": f"Invalid JSON output from runner: {output}"}

    except subprocess.TimeoutExpired:
        return {
            "status": "Time Limit Exceeded",
            "message": f"Execution took longer than {_EXECUTION_TIMEOUT_SECONDS} seconds",
        }
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
