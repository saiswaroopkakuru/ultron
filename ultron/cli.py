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

if __name__ == "__main__":
    main()
