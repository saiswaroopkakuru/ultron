import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import json
from mcp.server.fastmcp import FastMCP
from ultron.core.breadcrumb import breadcrumb_store
from ultron.core.pruner import pruner
from ultron.core.router import router
from ultron.config import config

mcp = FastMCP(
    "Ultron Optimizer",
    instructions="Context-aware plugin router, reversible tool-output pruner, and Karpathy coding guidelines."
)

# -----------------
# CONTEXT ROUTER & ECOSYSTEM TOOLS
# -----------------

@mcp.tool()
def ultron_route_context(prompt_or_context: str) -> str:
    """
    Intelligently analyzes the current prompt or context and returns
    which plugins (Headroom pruner, Caveman density, Claude-Mem, Karpathy guidelines)
    and specialized Claude skills (TDD, verification-loop, etc.) to activate.
    """
    decision = router.route_context(prompt_or_context)
    lines = [
        f"=== ULTRON CONTEXT ROUTER DECISION ===",
        f"Primary Plugin:     {decision['primary_plugin']}",
        f"Active Plugins:     {', '.join(decision['active_plugins'])}",
        f"Recommended Skills: {', '.join(decision['recommended_skills']) if decision['recommended_skills'] else 'none'}",
        "\nDirectives:"
    ]
    for d in decision['directives']:
        lines.append(f"  * {d}")
    return "\n".join(lines)

@mcp.tool()
def ultron_get_active_plugins() -> str:
    """
    Returns the discovery status of all installed ecosystem plugins and skills
    on this machine (Headroom, Caveman, Claude-Mem, Karpathy, and Claude skills).
    """
    status = router.get_plugin_status()
    lines = ["=== ULTRON ECOSYSTEM PLUGINS & SKILLS ==="]
    for key in ["headroom_pruner", "caveman", "claude_mem", "karpathy_guidelines"]:
        info = status[key]
        lines.append(f"- **{info['name']}** [{info['status']}]: {info['role']} (Layer: {info['layer']})")
    
    skills_info = status["claude_skills"]
    lines.append(f"\nInstalled Claude Skills ({skills_info['count']}):")
    for s in skills_info['available']:
        lines.append(f"  * {s}")
    return "\n".join(lines)


# -----------------
# CONTEXT PRUNING & RECOVERY TOOLS
# -----------------

@mcp.tool()
def ultron_compress_tool_output(content: str, content_type: str = "auto") -> str:
    """
    Prunes heavy tool outputs (build/test logs, git diffs, JSON payloads, large docs)
    (benchmark fixtures: 93% on build logs, 89% on git diffs, 99% on JSON, 0% on source code).
    Stores the uncompressed raw output in the reversible Breadcrumb store
    and returns an optimized summary with a breadcrumb hash tag [ultron:ref:hash:NL:NB].
    """
    compressed, meta = pruner.prune_tool_output(content)
    tag = meta.get("breadcrumb", "")
    savings = meta.get("savings_pct", 0.0)
    return (
        f"--- ULTRON PRUNED ({savings:.1f}% reduction) ---\n"
        f"{compressed}\n"
        f"--- (Use ultron_expand_breadcrumb('{tag}') if full details are needed) ---"
    )

@mcp.tool()
def ultron_expand_breadcrumb(ref_tag_or_hash: str) -> str:
    """
    Losslessly recovers and returns the full raw uncompressed content
    stored behind an [ultron:ref:...] hash key from local SQLite storage.
    """
    clean = ref_tag_or_hash.replace("[", "").replace("]", "").replace("ultron:ref:", "").split(":")[0].strip()
    raw = breadcrumb_store.retrieve(clean)
    if raw is None:
        return f"Error: Hash '{clean}' not found in breadcrumb store."
    return raw

@mcp.tool()
def ultron_get_status() -> str:
    """
    Returns live telemetry metrics on tokens ingested, tokens pruned,
    percentage reduced, tool calls intercepted, and system storage.
    """
    telemetry = breadcrumb_store.get_telemetry()
    return (
        f"Ultron In-Process Context Pruner Status:\n"
        f"- Status: Active (PostToolUse Hook enabled)\n"
        f"- Total Tokens Ingested: {telemetry['total_tokens_in']:,}\n"
        f"- Tokens Saved: {telemetry['tokens_saved']:,} ({telemetry['savings_percentage']}%)\n"
        f"- Total Raw Bytes Ingested: {telemetry['total_raw_bytes']:,} bytes\n"
        f"- Total Bytes Pruned: {telemetry['total_pruned_bytes']:,} bytes\n"
        f"- Tool Calls Intercepted: {telemetry['tool_calls_intercepted']:,}\n"
        f"- Breadcrumb Expansions: {telemetry['expansions_count']:,}\n"
        f"- Database Path: {breadcrumb_store.db_path}"
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
            f"run '/compact' to reset context cleanly at a natural boundary."
        )
    return (
        f"[No compaction needed]: {tool_invocations_count}/{threshold} tool calls used. "
        f"Continue current work."
    )

@mcp.tool()
def ultron_cl4r1t4s_scaffold(mode: str = "frontier_unified") -> str:
    """
    Returns production-grade agent scaffolding extracted from CL4R1T4S.
    Supported modes:
    - 'frontier_unified': Synthesis of Anthropic Concise Mode, Cursor 2.0, Devin 2.0 & Karpathy.
    - 'concise_mode': Anthropic's official Concise Mode prompt (UserStyle_Modes.md).
    - 'devin_mode': Devin 2.0 root-cause isolation & truthful engineering directives.
    - 'cursor_mode': Cursor Composer 2.0 speculative reads, 3-strike loop guard, & single-pass edits.
    """
    if mode == "concise_mode":
        return (
            "[ANTHROPIC CONCISE MODE - FROM CL4R1T4S]\n"
            "Claude is operating in Concise Mode. In this mode, Claude aims to reduce its output tokens while maintaining "
            "its helpfulness, quality, completeness, and accuracy. Claude provides answers to questions without much "
            "unneeded preamble or postamble. It focuses on addressing the specific query or task at hand, avoiding tangential "
            "information unless helpful for understanding or completing the request. If it decides to create a list, Claude focuses "
            "on key information instead of comprehensive enumeration. Claude maintains a helpful tone while avoiding excessive "
            "pleasantries or redundant offers of assistance. For code, artifacts, written content, or other generated outputs, "
            "Claude maintains the exact same level of quality, completeness, and functionality as when NOT in Concise Mode. "
            "There should be no impact to these output types. Claude does not compromise on completeness, correctness, "
            "appropriateness, or helpfulness for the sake of brevity."
        )
    elif mode == "devin_mode":
        return (
            "[DEVIN 2.0 AUTONOMOUS ENGINEERING DIRECTIVE - FROM CL4R1T4S]\n"
            "1. ROOT-CAUSE ISOLATION: When struggling to pass tests, never modify the tests themselves unless explicitly requested. "
            "Always first consider that the root cause is in the implementation under test.\n"
            "2. TRUTHFUL & TRANSPARENT: Do not create fake sample data or mock tests when you cannot get real data. "
            "Do not pretend broken code is working.\n"
            "3. ZERO CODE COMMENTS: Do not add comments, docstrings, or inline explanations to code you write unless requested. "
            "Keep code clean and concise.\n"
            "4. MODES: Operate strictly in 'planning' mode (gather context, inspect LSP/codebase) before transitioning to 'edit' mode.\n"
            "5. OUTPUT TRUNCATION: Long terminal outputs must be truncated and offloaded to local storage rather than dumped into context."
        )
    elif mode == "cursor_mode":
        return (
            "[CURSOR COMPOSER 2.0 DIRECTIVE - FROM CL4R1T4S]\n"
            "1. 3-STRIKE LOOP BREAKER: Do not loop more than 3 times to fix linter or test errors on the same file. "
            "Stop, step back, and isolate the root cause or ask user.\n"
            "2. SPECULATIVE BATCH READS: Speculatively read multiple relevant files in parallel rather than serial round-trips.\n"
            "3. SINGLE-PASS UNIFIED EDITS: Always combine all changes into a single edit invocation rather than fragmented updates.\n"
            "4. SURGICAL MUTATION: Always prefer editing existing files. Never proactively create documentation or README files.\n"
            "5. NON-INTERACTIVE TERMINAL: Pass non-interactive flags (--yes, -y) and pipe pagers to `| cat`."
        )
    else:
        return (
            "[ULTRON FRONTIER UNIFIED SCAFFOLD - CL4R1T4S SYNTHESIS]\n"
            "1. INTENT GATE: Distinguish DIAGNOSTIC (read-only evidence) from IMPLEMENTATION (active code changes).\n"
            "2. CONCISE MODE: Eliminate preamble/postamble. Keep code 100% complete, bug-free, and runnable.\n"
            "3. ZERO CODE BLOAT: No unrequested docstrings or inline commentary in generated code.\n"
            "4. 3-STRIKE RULE: Abort automated fix loops after 3 failures on the same error. Isolate root cause.\n"
            "5. SURGICAL EDITS: Read before write, batch changes into single-pass edits, touch only requested lines.\n"
            "6. VERIFIABLE GOAL: Build, lint, and run automated tests before and after changes. Never relax tests."
        )

# -----------------
# RESOURCES & PROMPTS
# -----------------

@mcp.resource("ultron://metrics")
def get_metrics_resource() -> str:
    """Live token savings telemetry JSON."""
    return json.dumps(breadcrumb_store.get_telemetry(), indent=2)

@mcp.prompt("frontier_unified")
def prompt_frontier_unified() -> str:
    """Master frontier agent scaffold synthesizing Anthropic Concise Mode, Cursor 2.0, Devin 2.0, and Karpathy."""
    return ultron_cl4r1t4s_scaffold("frontier_unified")

@mcp.prompt("cl4r1t4s_concise_mode")
def prompt_cl4r1t4s_concise_mode() -> str:
    """Anthropic's official Concise Mode system prompt extracted from CL4R1T4S."""
    return ultron_cl4r1t4s_scaffold("concise_mode")

@mcp.prompt("cl4r1t4s_devin_mode")
def prompt_cl4r1t4s_devin_mode() -> str:
    """Devin 2.0 autonomous engineering directive extracted from CL4R1T4S."""
    return ultron_cl4r1t4s_scaffold("devin_mode")

@mcp.prompt("cl4r1t4s_cursor_mode")
def prompt_cl4r1t4s_cursor_mode() -> str:
    """Cursor Composer 2.0 3-strike loop guard & batch edit directive extracted from CL4R1T4S."""
    return ultron_cl4r1t4s_scaffold("cursor_mode")

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

