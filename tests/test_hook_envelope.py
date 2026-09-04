"""
End-to-end tests for the PostToolUse hook envelope.

The hook rewrites Claude Code's own tool-result objects, so it has to emit the
exact shape Claude Code parses back: a `hookSpecificOutput` wrapper whose
`updatedToolOutput` still matches the tool's output schema. If that shape ever
drifts, the replacement is rejected and the hook silently stops pruning
anything. These tests drive the real hook as a subprocess over stdin, the same
way Claude Code invokes it, so the drift shows up as a failing test.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "ultron" / "hooks" / "post_tool_use.py"


@pytest.fixture
def hook_env(tmp_path):
    """Run the hook against a throwaway breadcrumb DB, never the user's live one."""
    env = dict(os.environ)
    env["ULTRON_DB_PATH"] = str(tmp_path / "hook.db")
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_hook(payload, env):
    """Invoke the hook exactly as Claude Code does: JSON on stdin, JSON on stdout."""
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
    )
    assert proc.returncode == 0, f"hook exited {proc.returncode}: {proc.stderr}"
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)


def noisy_build_log(lines=200):
    body = "\n".join(
        f"[info] [webpack-dev-server] Processing module {i}/{lines}... [100%] unchanged"
        for i in range(lines)
    )
    return (
        "pytest -q\n"
        + body
        + "\nE       AssertionError: assert 200 == 401\n"
        + "FAILED tests/test_webhook.py::test_payment_webhook_auth\n"
        + "1 failed, 149 passed in 4.21s\n"
    )


def test_bash_output_keeps_claude_code_schema(hook_env):
    """Bash results must come back as {stdout, stderr, interrupted}, not a bare string."""
    result = run_hook({
        "tool_name": "Bash",
        "response": {"stdout": noisy_build_log(), "stderr": "", "interrupted": False},
    }, hook_env)

    assert result is not None, "hook produced no replacement for a 200-line build log"
    specific = result["hookSpecificOutput"]
    assert specific["hookEventName"] == "PostToolUse"

    updated = specific["updatedToolOutput"]
    assert isinstance(updated, dict), "Bash replacement must stay an object"
    assert set(["stdout", "stderr", "interrupted"]).issubset(updated.keys())
    assert isinstance(updated["stdout"], str)
    assert isinstance(updated["stderr"], str)
    assert isinstance(updated["interrupted"], bool)

    # Pruning has to keep the line that explains the failure, and hand back a
    # breadcrumb for the rest.
    assert "AssertionError: assert 200 == 401" in updated["stdout"]
    assert "[ultron:ref:" in updated["stdout"]
    assert len(updated["stdout"]) < len(noisy_build_log())


def test_bash_optional_fields_survive(hook_env):
    """Background-task fields Claude Code sets must not be dropped by the rewrite."""
    result = run_hook({
        "tool_name": "Bash",
        "response": {
            "stdout": noisy_build_log(),
            "stderr": "warning: deprecated flag\n",
            "interrupted": False,
            "backgroundTaskId": "task-42",
        },
    }, hook_env)

    updated = result["hookSpecificOutput"]["updatedToolOutput"]
    assert updated["backgroundTaskId"] == "task-42"
    assert updated["stderr"] == "warning: deprecated flag\n"


def test_read_output_keeps_file_envelope(hook_env):
    """Read results must stay {type, file:{...}} with numLines matching the new content."""
    log_text = noisy_build_log()
    result = run_hook({
        "tool_name": "Read",
        "response": {
            "type": "text",
            "file": {
                "filePath": "/tmp/build.log",
                "content": log_text,
                "numLines": log_text.count("\n") + 1,
                "startLine": 1,
                "totalLines": log_text.count("\n") + 1,
            },
        },
    }, hook_env)

    assert result is not None
    updated = result["hookSpecificOutput"]["updatedToolOutput"]
    assert updated["type"] == "text"
    assert isinstance(updated["file"], dict)
    assert updated["file"]["filePath"] == "/tmp/build.log"
    assert updated["file"]["numLines"] == updated["file"]["content"].count("\n") + 1


def test_source_code_is_left_alone(hook_env):
    """Code must reach the model byte-identical, so the hook should stay silent."""
    source = (REPO_ROOT / "ultron" / "core" / "pruner.py").read_text(encoding="utf-8")
    result = run_hook({
        "tool_name": "Read",
        "response": {
            "type": "text",
            "file": {"filePath": "ultron/core/pruner.py", "content": source,
                     "numLines": source.count("\n") + 1, "startLine": 1,
                     "totalLines": source.count("\n") + 1},
        },
    }, hook_env)

    assert result is None, "source code was rewritten; it must pass through untouched"


def test_short_output_is_left_alone(hook_env):
    result = run_hook({
        "tool_name": "Bash",
        "response": {"stdout": "ok\n", "stderr": "", "interrupted": False},
    }, hook_env)
    assert result is None


def test_already_pruned_output_is_not_recompressed(hook_env):
    already = "[ultron:ref:deadbeef:200L:9000B]\n" + "summary line\n" * 40
    result = run_hook({
        "tool_name": "Bash",
        "response": {"stdout": already, "stderr": "", "interrupted": False},
    }, hook_env)
    assert result is None


def test_malformed_payload_never_breaks_the_session(hook_env):
    """A hook crash would stall the tool loop, so bad input must exit 0 and stay quiet."""
    for raw in ["", "not json at all", json.dumps({"tool_name": "Bash"})]:
        proc = subprocess.run(
            [sys.executable, str(HOOK)],
            input=raw, capture_output=True, text=True, encoding="utf-8",
            env=hook_env, timeout=60,
        )
        assert proc.returncode == 0
        assert proc.stdout.strip() == ""


def test_breadcrumb_from_hook_expands_byte_exact(hook_env):
    """The whole point of pruning: the original is recoverable, not lost."""
    log_text = noisy_build_log()
    result = run_hook({
        "tool_name": "Bash",
        "response": {"stdout": log_text, "stderr": "", "interrupted": False},
    }, hook_env)

    stdout = result["hookSpecificOutput"]["updatedToolOutput"]["stdout"]
    tag_start = stdout.index("[ultron:ref:")
    hash_key = stdout[tag_start:].split(":")[2]

    os.environ["ULTRON_DB_PATH"] = hook_env["ULTRON_DB_PATH"]
    from ultron.core.breadcrumb import BreadcrumbStore
    store = BreadcrumbStore(db_path=hook_env["ULTRON_DB_PATH"])

    assert store.retrieve(hash_key) == log_text
