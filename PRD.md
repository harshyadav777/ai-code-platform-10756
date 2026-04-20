# Product Requirements Document — AI Coder Platform

## 1. Overview

The **AI Coder Platform** is a local, browser-based coding practice environment that lets students solve programming challenges and receive instant, AI-powered feedback. It supports multiple question types and uses Google Gemini to deliver blunt, direct code reviews.

## 2. Problem Statement

Students learning to code lack a practice tool that:

- Evaluates code correctness **and** algorithmic quality in one step.
- Provides **honest, detailed feedback** rather than generic pass/fail.
- Supports question formats beyond coding (MCQs, open-ended, predict-the-bug).

## 3. Target Users

- **Primary:** Computer Science students (intro–intermediate level).
- **Secondary:** Educators who want a self-hostable quiz/assessment tool.

## 4. Core Features

### 4.1 Multi-Format Questions

| Type                                                               | Description                                                              |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| `CODING`                                                           | Write a function, run against hidden test cases, profile time complexity |
| `FIND_REPLACE`                                                     | Predict the output of buggy code, then fix it                            |
| `MCQ_THEORY` / `MCQ_CODING` / `MCQ_REAL_WORLD` / `MULTIPLE_CHOICE` | Single-choice multiple-choice                                            |
| `OPEN_ENDED`                                                       | Free-text response graded against a rubric                               |

### 4.2 Automated Test Execution

- User code is executed in an isolated subprocess with a 5-second timeout.
- Test case results (input, expected, actual, pass/fail) are returned per-case.

### 4.3 Time Complexity Profiling

- Uses the `big_o` library to empirically measure time complexity.
- Reports Big-O notation (e.g., O(N), O(N log N)) on accepted solutions.

### 4.4 AI Feedback (Gemini)

- **Coding:** Identifies the algorithm used, critiques complexity, suggests style improvements.
- **Open-ended:** Grades free-text answers against a rubric.
- **Find & Replace:** Validates whether the student's output prediction is correct.
- Tone: strict, blunt, no-nonsense — like a rigorous code reviewer.

### 4.5 Interactive IDE

- Monaco editor with Python syntax highlighting.
- Inline error highlighting (red gutter marker on the offending line).
- Keyboard shortcut: `Cmd/Ctrl + Enter` to submit.
- Resizable panels (problem description ↔ workspace ↔ console).

### 4.6 Session State

- Per-problem state (code, selections, results) persists across problem navigation within a session.
- Global session timer tracks elapsed time.

## 5. Non-Functional Requirements

| Requirement            | Target                                  |
| ---------------------- | --------------------------------------- |
| Deployment             | Local only (dev server)                 |
| Code execution timeout | 5 seconds                               |
| Browser support        | Modern Chrome / Firefox / Safari        |
| API key                | User-supplied Gemini API key via `.env` |

## 6. Out of Scope (v1)

- User authentication / accounts
- Persistent storage / database
- Leaderboards or scoring
- Custom problem authoring UI (problems are edited as JSON)
- Multi-language support (Python only)
- Production deployment / hosting

## 7. Success Criteria

- Students can complete all 13 problems end-to-end.
- AI feedback is returned within 10 seconds of submission.
- Error highlighting correctly points to the offending line in user code.
