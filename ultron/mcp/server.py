import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import json
from mcp.server.fastmcp import FastMCP
from ultron.core.breadcrumb import breadcrumb_store
from ultron.core.claudemem import claudemem
from ultron.core.headroom import headroom
from ultron.core.caveman import caveman
from ultron.core.omniroute import omniroute
from ultron.config import config

mcp = FastMCP(
    "Ultron Optimizer",
    instructions="Reversible tool-output compression, breadcrumb recovery, persistent memory, and Karpathy coding guidelines."
)

# -----------------
# TOKEN OPTIMIZATION TOOLS
# -----------------

@mcp.tool()
def ultron_compress_tool_output(content: str, content_type: str = "auto") -> str:
    """
    Compresses heavy tool outputs (build logs, git diffs, test outputs, JSON)
    by 90%+ when the output is repetitive, less otherwise. Stores the uncompressed raw output in the reversible Breadcrumb store
    and returns the optimized summary with a breadcrumb hash tag [ultron:ref:...].
    """
    compressed, meta = headroom.compress_tool_output(content)
    tag = meta.get("breadcrumb", "")
    savings = meta.get("savings_pct", 0.0)
    return (
        f"--- ULTRON COMPRESSED ({savings:.1f}% reduction) ---\n"
        f"{compressed}\n"
        f"--- (Use ultron_expand_breadcrumb('{tag}') if full details are needed) ---"
    )

@mcp.tool()
def ultron_expand_breadcrumb(ref_tag_or_hash: str) -> str:
    """
    Losslessly recovers and returns the full raw uncompressed content
    stored behind an [ultron:ref:...] hash key.
    """
    clean = ref_tag_or_hash.replace("[", "").replace("]", "").replace("ultron:ref:", "").split(":")[0].strip()
    raw = breadcrumb_store.retrieve(clean)
    if raw is None:
        return f"Error: Hash '{clean}' not found in breadcrumb store."
    return raw

@mcp.tool()
def ultron_recall_memory(query: str, project_dir: str = "", limit: int = 5) -> str:
    """
    Searches persistent cross-session memory for architectural decisions,
    past debugging fixes, and project context using local zero-cost token matching.
    """
    memories = claudemem.recall_memories(query, project_dir=project_dir, limit=limit)
    if not memories:
        return "No matching memories found in Ultron memory store."
    
    formatted = ["Found memories in Ultron persistent store:"]
    for m in memories:
        formatted.append(f"- **{m['topic']}**: {m['content']} (Tags: {m.get('tags', '')})")
    return "\n".join(formatted)

@mcp.tool()
def ultron_save_memory(topic: str, content: str, tags: str = "", project_dir: str = "", importance: int = 1) -> str:
    """
    Permanently records an architectural decision, coding convention, or bug fix
    into cross-session persistent memory so future agent turns never repeat mistakes.
    """
    claudemem.save_memory(topic=topic, content=content, tags=tags, project_dir=project_dir, importance=importance)
    return f"Successfully recorded persistent memory for topic: '{topic}'."

@mcp.tool()
def ultron_checkpoint_session(summary: str, session_id: str = "", project_dir: str = "", active_branch: str = "") -> str:
    """
    Checkpoints current session state (CPR: Compress, Preserve, Resume),
    saving key milestone context for instant resumption in future sessions.
    """
    sid = session_id or "session_" + str(int(claudemem.db_path.stat().st_mtime))
    claudemem.checkpoint_session(sid, summary, project_dir=project_dir, active_branch=active_branch)
    return f"Checkpoint saved for session {sid}."

@mcp.tool()
def ultron_caveman_compress(text: str, mode: str = "adaptive") -> str:
    """
    Applies Caveman linguistic compression to prose while guaranteeing that
    all code blocks, inline code, filepaths, line numbers, and symbols remain 100% byte-exact.
    """
    c = caveman if mode == config.caveman_mode else type(caveman)(mode=mode)
    compressed, meta = c.compress_text(text)
    return compressed

@mcp.tool()
def ultron_get_status() -> str:
    """
    Returns live telemetry metrics on tokens ingested, tokens saved,
    percentage reduced, active model routing, and system health.
    """
    telemetry = omniroute.get_telemetry()
    return (
        f"Ultron Token Optimization Engine Status:\n"
        f"- Status: Active\n"
        f"- Total Tokens Ingested: {telemetry['total_tokens_in']:,}\n"
        f"- Tokens Saved (net): {telemetry['tokens_saved']:,} ({telemetry['savings_percentage']}%)\n"
        f"- Tokens Saved (gross): {telemetry['tokens_saved_gross']:,}\n"
        f"- Tokens Returned by expansions: {telemetry['tokens_expanded']:,}\n"
        f"- Active Local Open-Source Model: {telemetry['active_ollama_model']}\n"
        f"- Requests Routed: {json.dumps(telemetry['requests_routed'])}\n"
        f"- Storage Path: {config.db_path}"
    )

# -----------------
# KARPATHY & WORKFLOW TOOLS
# -----------------

@mcp.tool()
def ultron_karpathy_review(diff_or_code: str) -> str:
    """
    Reviews code against Andrej Karpathy's 4 core guidelines:
    1. Think Before Coding (surface hidden assumptions & tradeoffs)
    2. Simplicity First (anti-bloat check, no premature abstractions or speculative features)
    3. Surgical Changes (zero adjacent churn, touch only what you must, match repository style)
    4. Goal-Driven Execution (verifiable criteria, loop until tested)
    """
    checklist = [
        "### Andrej Karpathy Guidelines Review",
        "1. **Simplicity First**: Are there any abstractions created for single-use code? If yes, inline them.",
        "2. **Surgical Precision**: Does the change modify lines unrelated to the request? If yes, revert them.",
        "3. **Zero Speculation**: Are there unrequested 'future-proof' parameters or features? If yes, remove them.",
        "4. **Verifiable Goal**: Does the change have an automated test proving it works before and after?",
    ]
    # Check for over-engineering patterns
    warnings = []
    if "abstract class" in diff_or_code.lower() or "factory" in diff_or_code.lower():
        warnings.append("- Warning: Potential unnecessary abstraction detected. Can a simple function solve this?")
    if len(diff_or_code.splitlines()) > 150:
        warnings.append("- Warning: Large diff (>150 lines). Ask: Could this be written in 50 lines?")
    
    if warnings:
        checklist.append("\n**Heuristic Warnings:**\n" + "\n".join(warnings))
    else:
        checklist.append("\n**Heuristic Check:** No blatant over-engineering patterns detected.")
        
    return "\n".join(checklist)

@mcp.tool()
def ultron_strategic_compact_check(tool_invocations_count: int, threshold: int = 40) -> str:
    """
    Analyzes session depth and recommends whether to trigger strategic /compact
    at natural milestone boundaries instead of suffering arbitrary auto-compaction mid-task.
    """
    if tool_invocations_count >= threshold:
        return (
            f"[STRATEGIC COMPACTION RECOMMENDED]: You have reached {tool_invocations_count} tool calls.\n"
            f"If you have completed your current milestone (e.g. finished planning or passed tests),\n"
            f"save a checkpoint with ultron_checkpoint_session() and run '/compact' to reset context."
        )
    return f"Context within normal operating window ({tool_invocations_count}/{threshold} tool calls)."

# -----------------
# RESOURCES & PROMPTS
# -----------------

@mcp.resource("ultron://metrics")
def get_metrics_resource() -> str:
    """Live token savings telemetry JSON."""
    return json.dumps(omniroute.get_telemetry(), indent=2)

@mcp.resource("ultron://context/delta")
def get_context_delta() -> str:
    """Recent active project memory context."""
    latest = claudemem.get_latest_session()
    if latest:
        return f"Active Session: {latest['session_id']}\nSummary: {latest['summary']}"
    return "No active session checkpoint."

@mcp.prompt("karpathy_mode")
def prompt_karpathy() -> str:
    """Enforces Andrej Karpathy's 4 Rules for surgical, minimal, zero-bloat coding."""
    return (
        "[ANDREJ KARPATHY CODING DIRECTIVE ACTIVE]\n"
        "1. THINK BEFORE CODING: Surface assumptions and tradeoffs. If ambiguous, ask.\n"
        "2. SIMPLICITY FIRST: Minimum viable code. No speculative features or single-use abstractions.\n"
        "3. SURGICAL CHANGES: Touch only what you must. Match existing style. Zero adjacent churn.\n"
        "4. GOAL-DRIVEN: Define verifiable criteria and test until green."
    )

@mcp.prompt("verification_loop")
def prompt_verification_loop() -> str:
    """Enforces the 6-phase pre-PR verification loop."""
    return (
        "[VERIFICATION LOOP ACTIVE]\n"
        "Verify before declaring complete:\n"
        "1. Build passes cleanly.\n"
        "2. Type checker reports 0 new errors.\n"
        "3. Linter passes.\n"
        "4. Test suite green with 80%+ coverage.\n"
        "5. No credentials or secrets exposed.\n"
        "6. git diff shows only surgical changes directly requested."
    )

def run_mcp_server():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    run_mcp_server()
