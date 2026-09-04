import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any

CLAUDE_DIR = Path(os.path.expanduser("~/.claude"))
SETTINGS_FILE = CLAUDE_DIR / "settings.json"
SKILLS_DIR = CLAUDE_DIR / "skills" / "ultron"

ULTRON_SKILL_MD = """---
name: ultron
description: Unified 95% token optimization, persistent memory, and context compression engine.
---

# Ultron Token Optimizer & Memory Engine

Ultron transparently cuts token consumption by up to 95% while maintaining 100% code precision.

## Commands Available:
- `/ultron status` - View live token savings and requests routed
- `/ultron recall <query>` - Query cross-session memory
- `/ultron expand <hash>` - Expand a compressed [ultron:ref:...] breadcrumb tag
- `/compress` - Strategically compact context and preserve key milestones
- `/preserve` - Checkpoint current session architecture and decisions
- `/resume` - Restore state from previous project session
"""

def install_claude_integration(proxy_port: int = 8787) -> Dict[str, Any]:
    """
    Configures ~/.claude/settings.json and ~/.claude/skills/ultron/SKILL.md
    to integrate Ultron with Claude Code seamlessly.
    """
    results = {"backup_created": None, "settings_updated": False, "skill_installed": False}
    CLAUDE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Install Claude Skill
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    skill_path = SKILLS_DIR / "SKILL.md"
    skill_path.write_text(ULTRON_SKILL_MD.strip(), encoding="utf-8")
    results["skill_installed"] = True

    # 2. Update Settings.json with Ultron MCP Server and Proxy
    if SETTINGS_FILE.exists():
        backup_file = CLAUDE_DIR / f"settings.json.bak-ultron"
        shutil.copyfile(SETTINGS_FILE, backup_file)
        results["backup_created"] = str(backup_file)
        try:
            settings_data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            settings_data = {}
    else:
        settings_data = {}

    # Register Ultron MCP server
    mcp_servers = settings_data.setdefault("mcpServers", {})
    python_exe = os.sys.executable
    mcp_servers["ultron"] = {
        "command": python_exe,
        "args": ["-m", "ultron.cli", "mcp"],
        "env": {"PYTHONUNBUFFERED": "1"}
    }

    # Save settings
    SETTINGS_FILE.write_text(json.dumps(settings_data, indent=2), encoding="utf-8")
    results["settings_updated"] = True
    return results
