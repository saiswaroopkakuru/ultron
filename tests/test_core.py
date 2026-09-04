import pytest
from ultron.core.breadcrumb import breadcrumb_store
from ultron.core.headroom import headroom
from ultron.core.caveman import caveman
from ultron.core.claudemem import claudemem
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

def test_headroom_terminal_and_build_compression():
    lines = [f"[webpack] building module {i}... [ok]" for i in range(100)]
    lines.append("ERROR: src/api/user.ts(42,10): Property 'id' does not exist on type 'User'.")
    lines.append("npm ERR! Test failed. See above for more details.")
    raw_log = "\n".join(lines)

    compressed, meta = headroom.compress_tool_output(raw_log)
    assert meta["savings_pct"] > 50.0
    assert "ERROR: src/api/user.ts" in compressed
    assert "ultron:ref" in compressed

def test_headroom_git_diff_compression():
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

    compressed, meta = headroom.compress_tool_output(diff)
    assert meta["savings_pct"] > 30.0
    assert "new_value = 2" in compressed
    assert "unchanged lines" in compressed

def test_caveman_prose_fluff_removal_with_code_preservation():
    input_text = (
        "Sure, I would be happy to help with that! In order to solve this issue, "
        "you should update the function as follows:\n\n"
        "```python\ndef calculate_tax(amount: float, rate: float = 0.08) -> float:\n"
        "    return round(amount * rate, 2)\n```\n\n"
        "Please let me know if you need anything else! I hope this helps."
    )

    compressed, meta = caveman.compress_text(input_text)
    # Fluff removed
    assert "Sure, I would be happy" not in compressed
    assert "Please let me know if you need anything else" not in compressed
    # Code block 100% byte-exact preserved!
    assert "def calculate_tax(amount: float, rate: float = 0.08) -> float:" in compressed
    assert "return round(amount * rate, 2)" in compressed

def test_claudemem_save_and_recall():
    claudemem.save_memory(
        topic="Database Connection Pooling",
        content="Use SQLAlchemy pool_size=20 with max_overflow=10 to prevent connection timeouts.",
        tags="database,sqlalchemy,perf",
        project_dir="/workspace/backend"
    )

    results = claudemem.recall_memories("How should we configure SQLAlchemy connection pool?")
    assert len(results) > 0
    assert "SQLAlchemy pool_size=20" in results[0]["content"]

    delta = claudemem.generate_delta_context("pool connection timeouts")
    assert "Database Connection Pooling" in delta

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
    stabilized = cache_guard.stabilize_payload(payload, "[ULTRON MEMORY]")
    assert "You are an expert software engineer." in stabilized["system"]
    assert "[ULTRON MEMORY]" in stabilized["system"]

def test_karpathy_review_and_compact():
    from ultron.mcp.server import ultron_karpathy_review, ultron_strategic_compact_check

    review = ultron_karpathy_review("class FactoryBuilderAbstract: pass")
    assert "Andrej Karpathy Guidelines Review" in review
    assert "abstraction detected" in review

    compact_msg = ultron_strategic_compact_check(tool_invocations_count=45, threshold=40)
    assert "STRATEGIC COMPACTION RECOMMENDED" in compact_msg

def test_universal_prose_compression():
    prose = (
        "Certainly! I would be happy to help with that. In order to understand photosynthesis, "
        "it is important to keep in mind that plants use sunlight, water, and carbon dioxide. "
        "Due to the fact that plants are autotrophs, they produce their own food. "
        "At this point in time, researchers study this carefully. "
        "Please let me know if you need anything else! I hope this helps!"
    )
    compressed, meta = headroom.compress_tool_output(prose)
    assert meta["savings_pct"] > 20.0
    assert "photosynthesis" in compressed
    assert "plants use sunlight" in compressed
    assert "Certainly" not in compressed
    assert "Please let me know" not in compressed
