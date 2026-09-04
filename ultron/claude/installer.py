import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any

CLAUDE_DIR = Path(os.path.expanduser("~/.claude"))
SETTINGS_FILE = CLAUDE_DIR / "settings.json"
SKILLS_DIR = CLAUDE_DIR / "skills"
PACKAGE_SKILLS_DIR = Path(__file__).parent.parent / "skills"

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
    Configures ~/.claude/settings.json and copies all Ultron & Karpathy skills
    into ~/.claude/skills/ for instant availability in Claude Code.
    """
    results = {"backup_created": None, "settings_updated": False, "skills_installed": []}
    CLAUDE_DIR.mkdir(parents=True, exist_ok=True)
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Install primary Ultron skill
    ultron_skill_path = SKILLS_DIR / "ultron" / "SKILL.md"
    ultron_skill_path.parent.mkdir(parents=True, exist_ok=True)
    ultron_skill_path.write_text(ULTRON_SKILL_MD.strip(), encoding="utf-8")
    results["skills_installed"].append("ultron")

    # 2. Copy merged skills: karpathy-guidelines, strategic-compact, verification-loop, etc.
    if PACKAGE_SKILLS_DIR.exists():
        for skill_folder in PACKAGE_SKILLS_DIR.iterdir():
            if skill_folder.is_dir():
                target_folder = SKILLS_DIR / skill_folder.name
                target_folder.mkdir(parents=True, exist_ok=True)
                for item in skill_folder.glob("*"):
                    shutil.copyfile(item, target_folder / item.name)
                results["skills_installed"].append(skill_folder.name)

    # 3. Update Settings.json with Ultron MCP Server
    if SETTINGS_FILE.exists():
        backup_file = CLAUDE_DIR / "settings.json.bak-ultron"
        shutil.copyfile(SETTINGS_FILE, backup_file)
        results["backup_created"] = str(backup_file)
        try:
            settings_data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            settings_data = {}
    else:
        settings_data = {}

    mcp_servers = settings_data.setdefault("mcpServers", {})
    python_exe = os.sys.executable
    mcp_servers["ultron"] = {
        "command": python_exe,
        "args": ["-m", "ultron.cli", "mcp"],
        "env": {"PYTHONUNBUFFERED": "1"}
    }

    SETTINGS_FILE.write_text(json.dumps(settings_data, indent=2), encoding="utf-8")
    results["settings_updated"] = True
    return results
