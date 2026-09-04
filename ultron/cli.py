import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import os
import sys
import click
from datetime import datetime
from ultron.config import config
from ultron.core.breadcrumb import breadcrumb_store
from ultron.core.pruner import pruner

@click.group()
def main():
    """Ultron: High-performance context pruner & reversible breadcrumb store for Claude Code."""
    pass

@click.command()
def mcp():
    """Run the Ultron MCP stdio server."""
    from ultron.mcp.server import run_mcp_server
    run_mcp_server()

@click.command()
def status():
    """Display Ultron live telemetry and recent breadcrumbs."""
    telemetry = breadcrumb_store.get_telemetry()
    click.echo(click.style("\n=== ULTRON IN-PROCESS CONTEXT PRUNER ===", fg="cyan", bold=True))
    click.echo(f"  * Total Tokens Ingested:      {telemetry['total_tokens_in']:,}")
    click.echo(f"  * Tokens Pruned / Saved:      {telemetry['tokens_saved']:,}")
    click.echo(f"  * Context Reduction Ratio:    {telemetry['savings_percentage']}%")
    click.echo(f"  * Tool Calls Intercepted:     {telemetry['tool_calls_intercepted']:,}")
    click.echo(f"  * Breadcrumb Expansions:      {telemetry['expansions_count']:,}")
    click.echo(f"  * Database:                   {breadcrumb_store.db_path}")

    import sqlite3
    with sqlite3.connect(breadcrumb_store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        crumbs = conn.execute(
            "SELECT hash_key, content_type, char_len, line_count, created_at FROM breadcrumbs ORDER BY created_at DESC LIMIT 8"
        ).fetchall()
        total_crumbs = conn.execute("SELECT COUNT(*) FROM breadcrumbs").fetchone()[0]

    click.echo(click.style(f"\n=== RECENT BREADCRUMBS (showing {len(crumbs)} of {total_crumbs} stored) ===", fg="green", bold=True))
    if crumbs:
        click.echo(f"{'HASH':<10} {'TYPE':<16} {'SIZE':<18} {'TIME'}")
        click.echo("-" * 55)
        for c in crumbs:
            dt = datetime.fromtimestamp(c['created_at']).strftime("%H:%M:%S")
            size_str = f"{c['char_len']:,}ch / {c['line_count']}ln"
            click.echo(f"{c['hash_key']:<10} {c['content_type']:<16} {size_str:<18} {dt}")
    else:
        click.echo("  No breadcrumbs stored yet.")
    click.echo()

@click.command()
@click.argument("hash_key")
def expand(hash_key):
    """Retrieve and display raw uncompressed text for a breadcrumb hash."""
    raw = breadcrumb_store.retrieve(hash_key)
    if raw is None:
        click.echo(click.style(f"Error: Breadcrumb '{hash_key}' not found in store.", fg="red"))
        sys.exit(1)
    click.echo(raw)

@click.command()
@click.argument("input_path_or_text")
def compress(input_path_or_text):
    """Prune a log file, diff, JSON payload, or raw text and return the breadcrumb token."""
    if os.path.exists(input_path_or_text):
        with open(input_path_or_text, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read()
    else:
        raw_text = input_path_or_text

    pruned, meta = pruner.prune_tool_output(raw_text)
    raw_b = meta.get('raw_bytes', len(raw_text))
    comp_b = meta.get('compressed_bytes', len(pruned))
    pct = round(meta.get('savings_pct', 0.0), 2)
    click.echo(click.style(f"[ULTRON] Pruned {pct}% ({raw_b:,}B -> {comp_b:,}B)", fg="green", bold=True))
    click.echo(pruned)

@click.command()
@click.option("--days", default=7, help="Delete breadcrumbs older than N days")
def clean(days):
    """Purge breadcrumbs older than N days from SQLite storage."""
    deleted = breadcrumb_store.prune_old_breadcrumbs(days=days)
    click.echo(click.style(f"[OK] Cleaned {deleted} expired breadcrumbs older than {days} days.", fg="green"))

@click.command()
def install():
    """Install or verify Claude Code PostToolUse hook and MCP registration."""
    from ultron.claude.installer import install_claude_integration
    res = install_claude_integration()
    click.echo(click.style("[OK] Ultron Claude Code hook configured!", fg="green", bold=True))
    click.echo("  - Hook: PostToolUse installed in ~/.claude/settings.json")
    click.echo("  - MCP: Registered in ~/.claude.json")

@click.command()
@click.argument("text")
def route(text):
    """Analyze context and print optimal plugin and skill routing decisions."""
    from ultron.core.router import router
    decision = router.route_context(text)
    click.echo(click.style("\n=== ULTRON CONTEXT ROUTER DECISION ===", fg="cyan", bold=True))
    click.echo(f"  * Primary Plugin:     {decision['primary_plugin']}")
    click.echo(f"  * Active Plugins:     {', '.join(decision['active_plugins'])}")
    click.echo(f"  * Recommended Skills: {', '.join(decision['recommended_skills']) if decision['recommended_skills'] else 'none'}")
    click.echo(click.style("\nDirectives:", fg="green", bold=True))
    for d in decision['directives']:
        click.echo(f"  - {d}")
    click.echo()

@click.command()
def plugins():
    """Discover and display all installed ecosystem plugins and skills."""
    from ultron.core.router import router
    status = router.get_plugin_status()
    click.echo(click.style("\n=== ULTRON ECOSYSTEM PLUGINS ===", fg="cyan", bold=True))
    for key in ["headroom_pruner", "caveman", "claude_mem", "karpathy_guidelines"]:
        info = status[key]
        badge = click.style(f"[{info['status']}]", fg="green" if "active" in info['status'] else "yellow")
        click.echo(f"  * {info['name']:<28} {badge:<18} {info['role']}")
    
    skills_info = status["claude_skills"]
    click.echo(click.style(f"\n=== INSTALLED CLAUDE SKILLS ({skills_info['count']}) ===", fg="magenta", bold=True))
    for s in skills_info['available']:
        click.echo(f"  - {s}")
    click.echo()

@click.command()
@click.option("--breadcrumbs", is_flag=True, help="Also delete every stored breadcrumb (raw output is unrecoverable afterwards).")
@click.confirmation_option(prompt="Zero Ultron telemetry counters?")
def reset(breadcrumbs):
    """Zero the live telemetry counters. Use after a config change makes past numbers meaningless."""
    import sqlite3
    with sqlite3.connect(breadcrumb_store.db_path) as conn:
        conn.execute("""
            UPDATE telemetry SET total_tokens_in = 0, tokens_saved = 0, savings_percentage = 0.0,
                   tokens_expanded = 0, total_raw_bytes = 0, total_pruned_bytes = 0,
                   tool_calls_intercepted = 0, expansions_count = 0, updated_at = ?
            WHERE id = 'live'
        """, (datetime.now().timestamp(),))
        removed = 0
        if breadcrumbs:
            removed = conn.execute("SELECT COUNT(*) FROM breadcrumbs").fetchone()[0]
            conn.execute("DELETE FROM breadcrumbs")
    click.echo(click.style("Telemetry counters zeroed.", fg="green"))
    if breadcrumbs:
        click.echo(click.style(f"Deleted {removed:,} breadcrumbs.", fg="yellow"))


main.add_command(mcp)
main.add_command(status)
main.add_command(reset)
main.add_command(expand)
main.add_command(compress)
main.add_command(clean)
main.add_command(install)
main.add_command(route)
main.add_command(plugins)

if __name__ == "__main__":
    main()
