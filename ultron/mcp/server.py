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
    instructions="Unified 95% Token Optimization, Reversible Breadcrumbs, and Persistent Memory Engine."
)

# -----------------
# TOOLS
# -----------------

@mcp.tool()
def ultron_compress_tool_output(content: str, content_type: str = "auto") -> str:
    """
    Compresses heavy tool outputs (build logs, git diffs, test outputs, JSON)
    by up to 95%. Stores the uncompressed raw output in the reversible Breadcrumb store
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
        f"- Tokens Saved: {telemetry['tokens_saved']:,} ({telemetry['savings_percentage']}%\n"
        f"- Active Local Open-Source Model: {telemetry['active_ollama_model']}\n"
        f"- Requests Routed: {json.dumps(telemetry['requests_routed'])}\n"
        f"- Storage Path: {config.db_path}"
    )

# -----------------
# RESOURCES
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

# -----------------
# PROMPTS
# -----------------

@mcp.prompt("ultron_system_directive")
def prompt_directive() -> str:
    """High-density zero-waste communication directive."""
    return caveman.get_system_prompt_directive()

@mcp.prompt("ultron_session_resume")
def prompt_session_resume(project_dir: str = "") -> str:
    """Injects historical project context for seamless session resumption."""
    latest = claudemem.get_latest_session(project_dir=project_dir)
    summary = latest['summary'] if latest else "No previous checkpoint."
    return f"[ULTRON RESUME]: Restoring previous milestone:\n{summary}\nContinue from next step."

def run_mcp_server():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    run_mcp_server()
