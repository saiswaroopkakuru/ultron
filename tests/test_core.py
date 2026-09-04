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

def test_context_router():
    from ultron.core.router import router

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


