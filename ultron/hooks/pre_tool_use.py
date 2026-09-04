"""
Ultron PreToolUse Hook for Claude Code.
Intercepts heavy Bash commands before execution and wraps them with Ultron's cross-platform runner:
`python -m ultron.runner -- <command>`.

When executed, the runner captures stdout/stderr, prunes repetitive logs, test failures, and diffs,
stashes the byte-exact original into SQLite breadcrumbs, and returns the pruned output to Claude Code.
"""

import sys
import json
import re

PYTHON = sys.executable

HEAVY = re.compile(
    r"""(?x)
    \b(?:
        npm\s+(?:test|ci|install|run\s+\S+|build)
      | (?:yarn|pnpm|bun)\s+(?:test|build|install)
      | (?:python\s+-m\s+)?pytest
      | python\s+-m\s+(?!ultron\b)\S+
      | tox | nox
      | cargo\s+(?:build|test|check|clippy|run)
      | go\s+(?:build|test|run)
      | mvn | gradle | gradlew
      | tsc | webpack | rollup | esbuild | vite | next | nuxt | astro
      | docker\s+(?:build|compose\s+build|logs)
      | terraform\s+(?:plan|apply)
      | make(?:\s|$)
      | pip\s+install
      | git\s+log(?:\s+[^\n]*)?
      | git\s+show(?:\s+[^\n]*)?
      | cat\s+\S+
      | type\s+\S+
      | Get-Content\s+\S+
    )\b
    """
)

GIT_DIFF = re.compile(r"\bgit\s+(?:-\S+\s+)*diff\b")
GIT_DIFF_SUMMARY = re.compile(r"--(?:stat|name-only|name-status|shortstat|quiet)\b")
UNSAFE = re.compile(r"<<|&\s*$|\bexit\b|\btrap\b|\bexec\b|#[^\n]*$")

def should_rewrite(command: str) -> bool:
    if not command or "ultron.runner" in command or "ultron_compact" in command:
        return False
    stripped = command.strip()
    if UNSAFE.search(stripped):
        return False
    if HEAVY.search(stripped):
        return True
    return bool(GIT_DIFF.search(stripped)) and not GIT_DIFF_SUMMARY.search(stripped)

def wrap(command: str) -> str:
    return f'"{PYTHON}" -m ultron.runner -- {command}'

def run_hook():
    try:
        raw = sys.stdin.read()
        if not raw or not raw.strip():
            sys.exit(0)

        event = json.loads(raw)
        if event.get("tool_name") != "Bash":
            sys.exit(0)

        tool_input = event.get("tool_input") or {}
        command = tool_input.get("command", "")
        if not should_rewrite(command):
            sys.exit(0)

        wrapped = wrap(command)
        envelope = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "updatedInput": {**tool_input, "command": wrapped}
            }
        }
        sys.stdout.write(json.dumps(envelope) + "\n")
        sys.stdout.flush()
    except Exception:
        pass
    finally:
        sys.exit(0)

if __name__ == "__main__":
    run_hook()
