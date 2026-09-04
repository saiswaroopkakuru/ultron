import pytest
import json
from ultron.core.breadcrumb import breadcrumb_store
from ultron.core.pruner import pruner
from ultron.core.verifier import verifier
from ultron.core.cache_guard import cache_guard

def test_breadcrumb_store():
    sample_text = "This is a raw uncompressed terminal output\nwith multiple lines\nfor testing."
    hash_key, tag = breadcrumb_store.store(sample_text, content_type="test")
    assert hash_key in tag
    assert "ultron:ref" in tag
    
    retrieved = breadcrumb_store.retrieve(hash_key)
    assert retrieved == sample_text

    # Test expansion in text
    wrapped_text = f"Before output: {tag} After output."
    expanded = breadcrumb_store.expand_breadcrumbs_in_text(wrapped_text)
    assert sample_text in expanded
    assert "[ultron:ref:" not in expanded

def test_breadcrumb_collision_extends_key_without_data_loss():
    import sqlite3
    fake_prefix = "deadbeef"
    original_content = "original content that must survive"
    with breadcrumb_store._connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO breadcrumbs (hash_key, raw_content, char_len, line_count, content_type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (fake_prefix, original_content, len(original_content), 1, "test", 0.0)
        )

    import ultron.core.breadcrumb as bc_module
    real_sha256 = bc_module.hashlib.sha256
    class _FakeDigest:
        def __init__(self, real): self._real = real
        def hexdigest(self):
            return fake_prefix + self._real.hexdigest()[8:]
    bc_module.hashlib.sha256 = lambda data: _FakeDigest(real_sha256(data))
    try:
        colliding_content = "different content that collides on the short prefix"
        new_key, tag = breadcrumb_store.store(colliding_content, content_type="test")
    finally:
        bc_module.hashlib.sha256 = real_sha256

    assert new_key != fake_prefix
    assert breadcrumb_store.retrieve(fake_prefix) == original_content
    assert breadcrumb_store.retrieve(new_key) == colliding_content

def test_pruner_terminal_and_build_compression():
    lines = [f"[webpack] building module {i}... [ok]" for i in range(100)]
    lines.append("ERROR: src/api/user.ts(42,10): Property 'id' does not exist on type 'User'.")
    lines.append("npm ERR! Test failed. See above for more details.")
    raw_log = "\n".join(lines)

    compressed, meta = pruner.prune_build_or_test_log(raw_log)
    assert meta["savings_pct"] > 50.0
    assert "ERROR: src/api/user.ts" in compressed
    assert "ultron:ref" in compressed

def test_pruner_git_diff_compression():
    diff_lines = [
        "diff --git a/app.py b/app.py",
        "--- a/app.py",
        "+++ b/app.py",
        "@@ -1,15 +1,15 @@"
    ]
    diff_lines.extend([f" context_line_{i} = {i}" for i in range(25)])
    diff_lines.append("-old_value = 1")
    diff_lines.append("+new_value = 2")
    diff_lines.extend([f" tail_line_{i} = {i}" for i in range(25)])
    diff = "\n".join(diff_lines)

    compressed, meta = pruner.prune_git_diff(diff)
    assert meta["savings_pct"] > 30.0
    assert "new_value = 2" in compressed
    assert "unchanged lines" in compressed

def test_prose_is_passed_through_untouched():
    """
    A resume mentioning pytest under skills was routed to the log pruner and came
    back as six lines. Unrecognized text must reach the model byte-identical.
    """
    resume = "\n".join([
        "Venkata Sai Swaroop Kakuru",
        "Software Engineer | Python, LLM Integration and RAG",
        "SUMMARY",
        "Software Engineer with 4+ years in Python shipping production systems.",
        "WORK EXPERIENCE",
        "Serve the fraud models in production on Amazon EKS at 100,000+ transactions a day.",
        "Inference cost came down through profiling first and quantizing second.",
        "SKILLS",
        "Quality and Risk: pytest, load testing, fault-injection drills, SonarQube in CI",
        "Cloud: AWS (EKS, Lambda, S3, IAM), Docker, Kubernetes, Terraform",
    ])

    out, meta = pruner.prune_tool_output(resume)

    assert out == resume
    assert meta["skipped"] == "unrecognized"
    assert meta["savings_pct"] == 0.0


def test_table_output_is_passed_through_untouched():
    """Repetitive line shapes are not permission to drop rows."""
    table = "\n".join([f"| row_{i:03d} | value_{i} | ok |" for i in range(60)])

    out, meta = pruner.prune_tool_output(table)

    assert out == table
    assert meta["skipped"] == "unrecognized"


def test_real_build_log_is_still_pruned():
    """The whitelist must still admit what it was built for."""
    log = "\n".join([f"webpack [info] building module {i}/60... [100%]" for i in range(60)])
    log += "\nERROR: src/api/user.ts(42,10): Property 'id' does not exist on type 'User'."

    compressed, meta = pruner.prune_tool_output(log)

    assert meta["type"] == "build_log"
    assert "ERROR: src/api/user.ts" in compressed


def test_short_log_is_not_pruned():
    """Below the line threshold the breadcrumb roundtrip costs more than it saves."""
    log = "\n".join([f"pytest collected item {i}" for i in range(12)])

    out, meta = pruner.prune_tool_output(log)

    assert out == log
    assert meta["skipped"] == "unrecognized"


def _unified_diff_body():
    lines = ["--- installed", "+++ repo", "@@ -2,14 +2,15 @@"]
    lines.extend([f" context_line_{i} = {i}" for i in range(30)])
    lines.append("-description: old wording that must survive pruning")
    lines.append("+description: new wording that must survive pruning")
    lines.extend([f" tail_line_{i} = {i}" for i in range(30)])
    return "\n".join(lines)


def test_router_detects_unified_diff_after_leading_output():
    """`diff -u` and difflib output rarely starts at byte 0. It is still a diff."""
    text = "DIFFERENT\n" + _unified_diff_body()

    compressed, meta = pruner.prune_tool_output(text)

    assert meta["type"] == "git_diff", f"routed to {meta.get('type')}, body would be dropped"
    assert "-description: old wording that must survive pruning" in compressed
    assert "+description: new wording that must survive pruning" in compressed


def test_router_detects_diff_without_file_headers():
    """A patch piped through grep or head keeps its hunks but loses --- / +++."""
    text = "\n".join(_unified_diff_body().splitlines()[2:])

    compressed, meta = pruner.prune_tool_output(text)

    assert meta["type"] == "git_diff"
    assert "+description: new wording that must survive pruning" in compressed


def test_diff_of_source_code_routes_to_diff_pruner():
    """
    A patch is mostly source lines, so the source guard claims it if it runs first.
    Diff pruning keeps every +/- line, so the diff check has to win.
    """
    diff = "\n".join([
        "diff --git a/service.py b/service.py",
        "--- a/service.py",
        "+++ b/service.py",
        "@@ -1,40 +1,40 @@",
        "import os",
        "from typing import Dict",
        "",
    ] + [f"    value_{i} = compute({i})" for i in range(40)] + [
        "-    return legacy_path(value_0)",
        "+    return new_path(value_0)",
    ])

    compressed, meta = pruner.prune_tool_output(diff)

    assert meta["type"] == "git_diff", f"routed to {meta.get('type') or meta.get('skipped')}"
    assert "+    return new_path(value_0)" in compressed
    assert "-    return legacy_path(value_0)" in compressed


def test_router_still_treats_plain_log_as_log():
    """The wider diff detection must not swallow ordinary build logs."""
    log = "\n".join([f"[webpack] building module {i}... [ok]" for i in range(80)])
    log += "\nERROR: src/api/user.ts(42,10): Property 'id' does not exist on type 'User'."

    _, meta = pruner.prune_tool_output(log)

    assert meta["type"] == "build_log"


def test_pruner_json_compression():
    payload = {
        "status": "success",
        "items": [{"id": i, "name": f"item_{i}", "details": {"active": True}} for i in range(50)]
    }
    raw_json = json.dumps(payload)
    compressed, meta = pruner.prune_json(raw_json)
    assert meta["savings_pct"] > 30.0
    assert "more items" in compressed
    assert "ultron:ref" in compressed

def test_pruner_document_text():
    doc = ("Important architectural note on microservices communication.\n" * 15)
    compressed, meta = pruner.prune_document_text(doc)
    assert meta["savings_pct"] > 20.0
    assert "Important architectural note" in compressed

def test_breadcrumb_telemetry():
    t_before = breadcrumb_store.get_telemetry()
    breadcrumb_store.record_savings(1000, 200)
    t_after = breadcrumb_store.get_telemetry()
    assert t_after["total_raw_bytes"] >= t_before["total_raw_bytes"] + 1000
    assert t_after["total_pruned_bytes"] >= t_before["total_pruned_bytes"] + 800

def test_verifier_precision():
    base_text = "Here is the code:\n```python\ndef add(a, b):\n    return a + b\n```"
    comp_text = "Code:\n```python\ndef add(a, b):\n    return a + b\n```"

    v = verifier.verify(base_text, comp_text)
    assert v["is_precision_passed"] is True
    assert v["code_precision_pct"] == 100.0
    assert v["syntax_valid"] is True

def test_cache_guard_stabilization():
    payload = {
        "model": "claude-3-7-sonnet-20250219",
        "system": "You are an expert software engineer.",
        "messages": [{"role": "user", "content": "Fix bug"}]
    }
    stabilized = cache_guard.stabilize_payload(payload, "[ULTRON CONTEXT]")
    assert "You are an expert software engineer." in stabilized["system"]
    assert "[ULTRON CONTEXT]" in stabilized["system"]

def test_karpathy_review_and_compact():
    from ultron.mcp.server import ultron_karpathy_review, ultron_strategic_compact_check

    review = ultron_karpathy_review("class FactoryBuilderAbstract: pass")
    assert "Andrej Karpathy Guidelines Review" in review
    assert "abstraction detected" in review

    compact_msg = ultron_strategic_compact_check(tool_invocations_count=45, threshold=40)
    assert "STRATEGIC COMPACTION RECOMMENDED" in compact_msg

    below_threshold_msg = ultron_strategic_compact_check(tool_invocations_count=10, threshold=40)
    assert isinstance(below_threshold_msg, str)
    assert "STRATEGIC COMPACTION RECOMMENDED" not in below_threshold_msg

def test_context_router(monkeypatch):
    from ultron.core.router import router

    monkeypatch.setattr(
        router, "_skills_cache",
        ["karpathy-guidelines", "security-guardrails", "strategic-compact",
         "tdd-workflow", "ultron", "verification-loop"]
    )

    # Test memory routing
    res_mem = router.route_context("What did we configure for database connection pooling last time?")
    assert "claude_mem" in res_mem["active_plugins"]

    # Test code and TDD routing
    res_code = router.route_context("Refactor the payment class and fix the failed unit test")
    assert "karpathy_guidelines" in res_code["active_plugins"]
    assert "tdd-workflow" in res_code["recommended_skills"]

    # Test verification loop
    res_pr = router.route_context("Ready to git commit and create PR")
    assert "verification-loop" in res_pr["recommended_skills"]

    # Test status
    status = router.get_plugin_status()
    assert "headroom_pruner" in status
    assert "claude_mem" in status
    assert "caveman" in status
    assert "karpathy_guidelines" in status

def test_ultron_runner():
    import subprocess
    proc = subprocess.run(
        ["python", "-m", "ultron.runner", "--", "python", "-c", "print('hello from runner')"],
        capture_output=True,
        text=True
    )
    assert proc.returncode == 0
    assert "hello from runner" in proc.stdout

def test_cl4r1t4s_frontier_scaffolding():
    from ultron.core.router import router
    from ultron.mcp.server import ultron_cl4r1t4s_scaffold

    # 1. Test Intent Gate
    diag_intent = router.classify_intent("Explain how the auth middleware works and check types")
    assert diag_intent == "DIAGNOSTIC"

    impl_intent = router.classify_intent("Implement rate limiting in the payment service and create tests")
    assert impl_intent == "IMPLEMENTATION"

    # 2. Test Complexity Classification
    single_shot = router.classify_complexity("What is the return type of foo()?", 35)
    assert single_shot["category"] == "SINGLE_SHOT_FACTUAL"
    assert single_shot["tool_budget"] == 1

    research = router.classify_complexity("Investigate codebase architecture and map dependencies", 55)
    assert research["category"] == "DEEP_RESEARCH"
    assert research["tool_budget"] >= 5

    edit = router.classify_complexity("Fix the bug in user service and refactor models", 45)
    assert edit["category"] == "SURGICAL_EDIT"

    # 3. Test MCP Prompts / Scaffold
    unified = ultron_cl4r1t4s_scaffold("frontier_unified")
    assert "INTENT GATE" in unified
    assert "CONCISE MODE" in unified
    assert "3-STRIKE RULE" in unified

    concise = ultron_cl4r1t4s_scaffold("concise_mode")
    assert "Concise Mode" in concise
    assert "maintains the exact same level of quality" in concise

    devin = ultron_cl4r1t4s_scaffold("devin_mode")

    assert "ROOT-CAUSE ISOLATION" in devin
    assert "ZERO CODE COMMENTS" in devin

    cursor = ultron_cl4r1t4s_scaffold("cursor_mode")
    assert "3-STRIKE LOOP BREAKER" in cursor
    assert "SPECULATIVE BATCH READS" in cursor

def test_omniroute_translation():
    from ultron.core.omniroute import omniroute

    anthropic_payload = {
        "model": "claude-3-7-sonnet-20250219",
        "system": "You are an assistant.",
        "messages": [
            {"role": "user", "content": "Run tests"},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "toolu_123", "name": "Bash", "input": {"command": "pytest"}}
                ]
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "toolu_123", "content": "12 passed"}
                ]
            }
        ],
        "tools": [
            {
                "name": "Bash",
                "description": "Run shell command",
                "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}}
            }
        ]
    }

    ollama_payload = omniroute.translate_anthropic_to_ollama(anthropic_payload)
    assert len(ollama_payload["messages"]) == 4 # 1 system + 3 messages
    assert ollama_payload["messages"][0]["role"] == "system"
    assert "tool_calls" in ollama_payload["messages"][2]
    assert ollama_payload["tools"][0]["function"]["name"] == "Bash"

def test_proxy_app_routes():
    from fastapi.testclient import TestClient
    from ultron.proxy.app import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert "telemetry" in data




