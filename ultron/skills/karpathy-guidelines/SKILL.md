---
name: karpathy-guidelines
description: Andrej Karpathy's 4 rules to eliminate LLM coding pitfalls. Enforces thinking before coding, minimum viable code, surgical changes without adjacent churn, and goal-driven test loops.
license: MIT
---

# Andrej Karpathy Coding Guidelines

Behavioral guidelines to prevent common LLM coding mistakes, derived from Andrej Karpathy's observations on AI coding agent pitfalls.

## 1. Think Before Coding
**Don't assume. Don't hide confusion. Surface tradeoffs.**
- State assumptions explicitly before writing code.
- If multiple interpretations exist, present them — do not pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, STOP. Name what is confusing and ask.

## 2. Simplicity First
**Minimum code that solves the problem. Nothing speculative.**
- No features beyond what was explicitly asked.
- No abstractions or factories for single-use code.
- No premature "flexibility" or configurability.
- No error handling for physically impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

## 3. Surgical Changes
**Touch only what you must. Clean up only your own mess.**
- Do not "improve" adjacent code, comments, or formatting.
- Do not refactor code that is not broken.
- Match existing repository style, even if you would do it differently.
- If your changes create unused imports or variables, clean them up.
- Never delete unrelated code. Every modified line must trace directly to the request.

## 4. Goal-Driven Execution
**Define success criteria. Loop until verified.**
- "Add validation" -> Write tests for invalid inputs, then make them pass.
- "Fix the bug" -> Write a test reproducing the bug, then make it pass.
- "Refactor X" -> Ensure tests pass both before and after changes.
- Loop independently against concrete verification gates.
