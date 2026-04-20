"""
LLM integration layer.

Provides three Gemini-backed helpers that return structured JSON:
  - generate_feedback  — algorithmic / style review for CODING problems
  - grade_open_ended   — rubric-based grading for OPEN_ENDED problems
  - validate_prediction — prediction checking for FIND_REPLACE problems
"""

import os
import json
from typing import Optional

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

_MODEL_NAME = "gemini-2.5-flash"


# ── Shared helpers ───────────────────────────────────────────────────

def _get_model() -> Optional[genai.GenerativeModel]:
    """Return a configured GenerativeModel, or None if the key is missing."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        return None
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(_MODEL_NAME)


def _parse_json_response(text: str) -> dict:
    """
    Strip optional markdown fences from an LLM response and parse JSON.

    Raises ``json.JSONDecodeError`` if the payload isn't valid JSON.
    """
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


# ── Public API ───────────────────────────────────────────────────────

def generate_feedback(user_code: str, problem_title: str, time_complexity: str) -> dict:
    """
    Ask the LLM to identify the algorithm, critique complexity, and
    suggest a style improvement for the submitted *user_code*.
    """
    model = _get_model()
    if not model:
        return {
            "algorithm_used": "Unknown (API Key missing)",
            "complexity_feedback": "Please add GEMINI_API_KEY to your backend/.env file to see AI feedback.",
            "style_suggestion": "",
        }

    prompt = f"""
You are an expert Python programming instructor.
A user submitted the following Python code for the problem: "{problem_title}".

User Code:
{user_code}

Empirical Time Complexity (measured via profiling): {time_complexity}

Task 1: Identify the standard algorithm or pattern used by the user (e.g., "Two Pointers", "BFS", "Dynamic Programming", "Brute Force", "Sorting", "Built-in max()").
Task 2: If the measured time complexity is worse than optimal, bluntly state why without sugarcoating it. If it is optimal, state it directly. Do not be overly encouraging or polite; be strict, blunt, and direct like a rigorous engineer reviewing code.
Task 3: Suggest one specific Pythonic code style improvement or optimization for this specific code. Do it forcefully and directly.

Return ONLY a valid JSON object with EXACTLY these keys (do not wrap in markdown tags like ```json):
{{"algorithm_used": "string", "complexity_feedback": "string", "style_suggestion": "string"}}
"""

    response = None
    try:
        response = model.generate_content(prompt)
        return _parse_json_response(response.text)
    except json.JSONDecodeError:
        raw = response.text if response else "N/A"
        return {
            "algorithm_used": "Error",
            "complexity_feedback": f"LLM returned invalid JSON. Raw response: {raw}",
            "style_suggestion": "",
        }
    except Exception as e:
        return {
            "algorithm_used": "Error",
            "complexity_feedback": f"LLM Feedback failed: {e}",
            "style_suggestion": "",
        }


def grade_open_ended(user_answer: str, rubric: str) -> dict:
    """Grade a free-text student answer against the given *rubric*."""
    model = _get_model()
    if not model:
        return {"status": "Error", "message": "API Key missing for grading."}

    prompt = f"""
You are a strict, blunt Computer Science professor. Grade the student's answer based on the provided rubric.

Rubric:
{rubric}

Student Answer:
{user_answer}

Provide extremely direct, no-nonsense feedback. Point out exactly what is wrong or missing. Do NOT be encouraging. Do NOT use polite pleasantries. Brutally and professionally point out flaws.

Return ONLY a valid JSON object:
{{"feedback": "string"}}
"""
    try:
        response = model.generate_content(prompt)
        return _parse_json_response(response.text)
    except Exception as e:
        return {"status": "Error", "feedback": f"Grading failed: {e}"}


def validate_prediction(prediction: str, expected: str) -> dict:
    """Check whether the student's output *prediction* matches *expected*."""
    model = _get_model()
    if not model:
        return {"status": "Error", "message": "API Key missing for prediction validation."}

    prompt = f"""
You are a strict code reviewer checking if a student correctly predicted the output of a buggy python function.

Expected Prediction logic/value:
{expected}

Student Prediction:
{prediction}

Determine if the student's prediction is logically correct based on the expected value. Provide direct, blunt, and strict feedback. Do not sugarcoat any errors. Return ONLY a valid JSON object.
{{"is_correct": boolean, "feedback": "Blunt explanation of why their prediction was right or wrong"}}
"""
    try:
        response = model.generate_content(prompt)
        return _parse_json_response(response.text)
    except Exception as e:
        return {"status": "Error", "is_correct": False, "feedback": f"Validation failed: {e}"}
