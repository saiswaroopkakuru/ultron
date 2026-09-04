import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
import os
import sys
import subprocess
import click
import uvicorn
from ultron.config import config
from ultron.claude.installer import install_claude_integration

@click.group()
def main():
    """Ultron: Unified 95% Token Optimization & Precision Gateway for Claude Code."""
    pass

@main.command()
@click.option("--host", default="127.0.0.1", help="Host to bind proxy")
@click.option("--port", default=8787, help="Port to bind proxy")
def start(host, port):
    """Start the Ultron AI proxy server."""
    click.echo(click.style(f"[*] Starting Ultron Token Optimization Gateway on http://{host}:{port}", fg="green", bold=True))
    click.echo(f"  - Upstream Anthropic: {config.anthropic_upstream}")
    click.echo(f"  - Local Ollama Engine: {config.ollama_url} ({config.ollama_model})")
    click.echo(f"  - Compression Mode: {config.caveman_mode}")
    uvicorn.run("ultron.proxy.app:app", host=host, port=port, log_level="info")

@main.command()
@click.argument("agent_args", nargs=-1)
def wrap(agent_args):
    """
    Wrap an agent (e.g. `ultron wrap claude`) with Ultron token optimization.
    Automatically sets ANTHROPIC_BASE_URL to point to Ultron.
    """
    if not agent_args:
        agent_args = ["claude"]

    cmd = list(agent_args)
    env = dict(os.environ)
    proxy_url = f"http://{config.host}:{config.port}"
    env["ANTHROPIC_BASE_URL"] = proxy_url
    env["CLAUDE_BASE_URL"] = proxy_url

    click.echo(click.style(f"[>] Ultron wrapping command: {' '.join(cmd)}", fg="cyan", bold=True))
    click.echo(f"  Target Proxy: {proxy_url}")

    try:
        subprocess.run(cmd, env=env)
    except KeyboardInterrupt:
        pass

@main.command()
def mcp():
    """Run the Ultron MCP stdio server."""
    from ultron.mcp.server import run_mcp_server
    run_mcp_server()

@main.command()
@click.option("--port", default=8787, help="Ultron proxy port")
def install_claude(port):
    """Install Ultron integration into Claude Code."""
    res = install_claude_integration(proxy_port=port)
    click.echo(click.style("[OK] Ultron Claude Code integration installed!", fg="green", bold=True))
    if res["backup_created"]:
        click.echo(f"  Backup: {res['backup_created']}")
    click.echo("  MCP Server: registered 'ultron' in ~/.claude/settings.json")
    click.echo("  Skill: installed to ~/.claude/skills/ultron/SKILL.md")
    click.echo("\nTo launch Claude Code with Ultron token optimization:")
    click.echo(click.style("  ultron wrap claude", fg="yellow", bold=True))

@main.command()
def bench():
    """Run Ultron benchmark evaluation against local Ollama."""
    import asyncio
    from benchmarks.run_ollama_eval import run_evaluation
    asyncio.run(run_evaluation())





@main.command()
def status():
    """Display Ultron live telemetry, breadcrumbs, and memory count."""
    import sqlite3
    from datetime import datetime
    db_path = str(config.db_path)
    if not os.path.exists(db_path):
        click.echo("Ultron database not found at " + db_path)
        return

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        click.echo(click.style("\n=== ULTRON STATUS & TELEMETRY ===", fg="cyan", bold=True))
        cur = conn.execute("SELECT * FROM telemetry WHERE id = 'live'")
        row = cur.fetchone()
        if row:
            click.echo(f"  * Total Tokens In:        {row['total_tokens_in']:,}")
            click.echo(f"  * Tokens Saved (Out):     {row['tokens_saved']:,}")
            click.echo(f"  * Token Reduction Ratio:  {row['savings_percentage']}%")
            click.echo(f"  * Requests Routed:        Anthropic: {row['requests_anthropic']} | Ollama: {row['requests_ollama']} | Fallback: {row['requests_fallback']}")
            click.echo(f"  * Active Local Engine:    {row['active_model']}")
        else:
            click.echo("  * Telemetry: Initializing (no traffic yet)")

        crumbs = conn.execute("SELECT hash_key, content_type, char_len, line_count, created_at FROM breadcrumbs ORDER BY created_at DESC LIMIT 6").fetchall()
        click.echo(click.style(f"\n=== BREADCRUMBS STASHED ({len(crumbs)} recent) ===", fg="green", bold=True))
        if crumbs:
            click.echo(f"{'HASH':<10} {'TYPE':<14} {'SIZE':<16} {'TIMESTAMP'}")
            click.echo("-" * 55)
            for c in crumbs:
                dt = datetime.fromtimestamp(c['created_at']).strftime("%H:%M:%S")
                size_str = f"{c['char_len']:,}ch / {c['line_count']}ln"
                click.echo(f"{c['hash_key']:<10} {c['content_type']:<14} {size_str:<16} {dt}")
        else:
            click.echo("  No breadcrumbs stashed yet.")

        mems = conn.execute("SELECT id, topic, content, tags, updated_at FROM memories ORDER BY updated_at DESC LIMIT 5").fetchall()
        click.echo(click.style(f"\n=== PERSISTENT MEMORIES ({len(mems)} recent) ===", fg="yellow", bold=True))
        if mems:
            for m in mems:
                preview = m['content'][:80].replace("\n", " ")
                topic = m['topic'] or 'general'
                click.echo(f"  [{topic.upper()}] {preview}...")
        else:
            click.echo("  No memories recorded yet.")
        click.echo()

@main.command()
@click.argument("hash_key")
def expand(hash_key):
    """Retrieve and display raw text for a breadcrumb hash."""
    from ultron.core.breadcrumb import breadcrumb_store
    raw = breadcrumb_store.retrieve(hash_key)
    if raw is None:
        click.echo(click.style(f"Error: Breadcrumb '{hash_key}' not found in store.", fg="red"))
        sys.exit(1)
    click.echo(raw)

@main.command()
@click.argument("query")
@click.option("--limit", default=3, help="Number of memories to recall")
def recall(query, limit):
    """Search cross-session persistent memory using BM25 relevance."""
    from ultron.core.claudemem import claudemem
    results = claudemem.recall_memories(query, limit=limit)
    if not results:
        click.echo(f"No memories matched query: '{query}'")
        return
    click.echo(click.style(f"Found {len(results)} relevant memories:", fg="cyan", bold=True))
    for i, r in enumerate(results, 1):
        click.echo(f"\n--- Result {i} [{r.get('topic', 'general').upper()}] ---")
        click.echo(r.get('content', ''))

@main.command()
@click.argument("content")
@click.option("--topic", default="decision", help="Topic: decision, architecture, bugfix, note")
def preserve(content, topic):
    """Checkpoint an architectural decision or milestone into persistent memory."""
    from ultron.core.claudemem import claudemem
    claudemem.save_memory(topic=topic, content=content)
    click.echo(click.style(f"[OK] Preserved [{topic}]: {content[:60]}...", fg="green"))

@main.command()
@click.argument("input_path_or_text")
def compress(input_path_or_text):
    """Compress a log file, diff, or raw text and return the breadcrumb token."""
    from ultron.core.headroom import headroom
    if os.path.exists(input_path_or_text):
        with open(input_path_or_text, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read()
    else:
        raw_text = input_path_or_text

    compressed, meta = headroom.compress_tool_output(raw_text)
    raw_b = meta.get('raw_bytes', len(raw_text))
    comp_b = meta.get('compressed_bytes', len(compressed))
    pct = round(meta.get('savings_pct', 0.0), 2)
    click.echo(click.style(f"Savings: {pct}% ({raw_b} -> {comp_b} bytes)", fg="green"))
    click.echo(compressed)

if __name__ == "__main__":
    main()
