"""
FastAPI application — AI Coder Platform backend.

Serves problem definitions and evaluates student submissions (coding,
MCQ, open-ended, and find-and-replace question types).
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json

from engine import run_and_profile_code
from llm import generate_feedback, grade_open_ended, validate_prediction

app = FastAPI(title="AI Coder Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ──────────────────────────────────────────────────────────

def _load_problems() -> list[dict]:
    """
    Read problems from the JSON file on every request.

    This is intentional — the file is tiny and it means new problems can
    be added without restarting the server.
    """
    with open("problems.json", "r") as f:
        return json.load(f)


def _find_problem(problem_id: str) -> dict:
    """Look up a problem by ID, or raise a 404."""
    problems = _load_problems()
    problem = next((p for p in problems if str(p["id"]) == str(problem_id)), None)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return problem


# ── Request schema ───────────────────────────────────────────────────

class CodeSubmission(BaseModel):
    problem_id: str
    code: Optional[str] = None
    selected_option_id: Optional[str] = None
    open_ended_response: Optional[str] = None
    predicted_output: Optional[str] = None


# ── Routes ───────────────────────────────────────────────────────────

@app.get("/api/problems")
async def list_problems():
    """Return a lightweight list of all problems (id, title, type)."""
    return [
        {"id": p["id"], "title": p["title"], "type": p["type"]}
        for p in _load_problems()
    ]


@app.get("/api/problem/{problem_id}")
async def get_problem(problem_id: str):
    """Return a single problem, with answer keys stripped out."""
    problem = _find_problem(problem_id)
    return {
        "id": problem["id"],
        "title": problem["title"],
        "description": problem["description"],
        "type": problem["type"],
        "signature": problem.get("signature"),
        "options": problem.get("options"),
    }


@app.post("/api/submit")
async def submit_answer(submission: CodeSubmission):
    """
    Evaluate a student submission.

    Dispatches to the appropriate handler based on the problem type:
    CODING, MCQ variants, OPEN_ENDED, or FIND_REPLACE.
    """
    problem = _find_problem(submission.problem_id)

    try:
        ptype = problem["type"]

        # ── Coding problems ──────────────────────────────────────
        if ptype == "CODING":
            if not submission.code:
                return {"status": "Error", "message": "Code is required"}

            result = run_and_profile_code(submission.code, problem["id"])

            if result.get("status") == "Accepted":
                result["llm_feedback"] = generate_feedback(
                    user_code=submission.code,
                    problem_title=problem["title"],
                    time_complexity=result.get("complexity_class", "Unknown"),
                )
            return result

        # ── Multiple-choice variants ─────────────────────────────
        if ptype in ("MCQ_THEORY", "MCQ_CODING", "MCQ_REAL_WORLD", "MULTIPLE_CHOICE"):
            if not submission.selected_option_id:
                return {"status": "Error", "message": "Selection required"}

            if submission.selected_option_id == problem["correct_option_id"]:
                return {"status": "Accepted", "message": "Correct! Excellent job."}
            return {"status": "Failed", "message": "Incorrect answer. Try again!"}

        # ── Open-ended ───────────────────────────────────────────
        if ptype == "OPEN_ENDED":
            if not submission.open_ended_response:
                return {"status": "Error", "message": "Response required"}

            assessment = grade_open_ended(submission.open_ended_response, problem["rubric"])
            return {
                "status": "Accepted",
                "llm_feedback": {
                    "complexity_feedback": assessment.get("feedback", "No feedback generated"),
                    "algorithm_used": "Open Ended Assessment",
                    "style_suggestion": "",
                },
            }

        # ── Find & replace (predict + fix) ───────────────────────
        if ptype == "FIND_REPLACE":
            if not submission.code or not submission.predicted_output:
                return {"status": "Error", "message": "Code and prediction required"}

            pred_validation = validate_prediction(submission.predicted_output, problem["rubric"])
            code_result = run_and_profile_code(submission.code, problem["id"])

            combined = code_result.copy()
            combined["prediction_feedback"] = pred_validation

            if not pred_validation.get("is_correct", False):
                combined["status"] = "Failed"
                combined["message"] = (
                    "Your code may have passed, but your prediction of the "
                    "buggy output was incorrect. Check AI Feedback."
                )
            elif code_result.get("status") == "Passed":
                combined["status"] = "Accepted"

            return combined

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Dev server ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
