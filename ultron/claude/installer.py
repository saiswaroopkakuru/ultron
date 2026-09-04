import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any

CLAUDE_DIR = Path(os.path.expanduser("~/.claude"))
SETTINGS_FILE = CLAUDE_DIR / "settings.json"
CLAUDE_JSON_FILE = Path(os.path.expanduser("~/.claude.json"))
SKILLS_DIR = CLAUDE_DIR / "skills"
PACKAGE_SKILLS_DIR = Path(__file__).parent.parent / "skills"

ULTRON_SKILL_MD = """---
name: ultron
description: Unified 95% token optimization, persistent memory, and reversible breadcrumb engine. Triggers on /ultron, /ultron status, /ultron expand <hash>, /ultron recall <query>, /ultron preserve, /compress, or /preserve.
---

# /ultron - Ultron Token Optimizer & Context Compression Engine

Ultron transparently slashes token consumption by up to 95% while guaranteeing 100% code and symbol precision. It combines:
1. **Reversible Breadcrumbs**: Large terminal logs, webpack traces, and git diffs are compacted into lightweight tags like `[ultron:ref:hash:NL:NB]`. Full raw output is stored in SQLite at `~/.ultron/memory.db` and can be expanded on-demand with zero loss.
2. **Persistent Cross-Session Memory**: Architectural decisions and bug fixes are stored in SQLite and queried via BM25 retrieval (~200 token injection vs 20k token history dumps).
3. **Smart Multi-Model Gateway & Telemetry**: Offloads summarization and indexing tasks to local Ollama (zero API tokens) and tracks live token savings.

---

## Instructions for the Assistant When Invoked

When the user types `/ultron` or any subcommand, execute the corresponding action immediately:

### 1. `/ultron` or `/ultron status`
Display the current live token savings, breadcrumbs, and memories.
- **If Ultron MCP tools are available**: Call `ultron_get_status()`.
- **Otherwise (or if running via CLI)**: Execute the shell command:
  ```powershell
  python -m ultron.cli status
  ```
Format the output cleanly for the user showing total tokens processed, tokens saved, percentage reduction, and the table of recent breadcrumbs.

### 2. `/ultron expand <hash>`
Expand a stashed breadcrumb back to its original raw output.
- **If Ultron MCP tools are available**: Call `ultron_expand_breadcrumb(hash_key="<hash>")`.
- **Otherwise**: Execute:
  ```powershell
  python -m ultron.cli expand <hash>
  ```
Print the exact raw uncompressed text so the user can inspect it.

### 3. `/ultron recall <query>`
Query cross-session memories by relevance.
- **If Ultron MCP tools are available**: Call `ultron_recall_memory(query="<query>")`.
- **Otherwise**: Execute:
  ```powershell
  python -m ultron.cli recall "<query>"
  ```
Present the retrieved decisions and context.

### 4. `/ultron preserve <content>` or `/preserve`
Checkpoint an important architecture decision, bug solution, or milestone to persistent memory.
- **If Ultron MCP tools are available**: Call `ultron_save_memory(topic="architecture", content="<content>")`.
- **Otherwise**: Execute:
  ```powershell
  python -m ultron.cli preserve "<content>" --topic "architecture"
  ```
Confirm to the user that the milestone is saved in `~/.ultron/memory.db`.

### 5. `/ultron compress <target>` or `/compress`
Compress a massive log file, diff, or text snippet.
- **If Ultron MCP tools are available**: Call `ultron_compress_tool_output(tool_output="<text>")`.
- **Otherwise**: Execute:
  ```powershell
  python -m ultron.cli compress "<target>"
  ```

---

## Relationship to Other Memory Systems
If other memory systems are present:
- **Project Memory (`~/.claude/projects/.../memory/`)**: Handles static developer preferences and high-level file descriptions.
- **`claude-mem` / `@modelcontextprotocol/server-memory`**: Handles entity/relation graphs.
- **`ultron`**: The heavy-data optimizer. Ultron stores raw blobs (diffs, test outputs, compiler traces) out-of-band in SQLite and replaces them with breadcrumbs, cutting prompt token consumption by up to 95%."""

def install_claude_integration(proxy_port: int = 8787) -> Dict[str, Any]:
    """
    Configures ~/.claude.json, ~/.claude/settings.json, and copies all Ultron
    & Karpathy skills into ~/.claude/skills/ for instant availability in Claude Code.
    """
    results = {"backup_created": None, "settings_updated": False, "skills_installed": []}
    CLAUDE_DIR.mkdir(parents=True, exist_ok=True)
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Install primary Ultron skill
    ultron_skill_path = SKILLS_DIR / "ultron" / "SKILL.md"
    ultron_skill_path.parent.mkdir(parents=True, exist_ok=True)
    ultron_skill_path.write_text(ULTRON_SKILL_MD.strip(), encoding="utf-8")
    results["skills_installed"].append("ultron")

    # 2. Copy merged skills
    if PACKAGE_SKILLS_DIR.exists():
        for skill_folder in PACKAGE_SKILLS_DIR.iterdir():
            if skill_folder.is_dir():
                target_folder = SKILLS_DIR / skill_folder.name
                target_folder.mkdir(parents=True, exist_ok=True)
                for item in skill_folder.glob("*"):
                    shutil.copyfile(item, target_folder / item.name)
                results["skills_installed"].append(skill_folder.name)

    # 3. Register Ultron MCP in ~/.claude.json
    python_exe = os.sys.executable
    repo_root = str(Path(__file__).parent.parent.parent.resolve())
    if CLAUDE_JSON_FILE.exists():
        try:
            claude_cfg = json.loads(CLAUDE_JSON_FILE.read_text(encoding="utf-8"))
        except Exception:
            claude_cfg = {}
        servers = claude_cfg.setdefault("mcpServers", {})
        servers["ultron"] = {
            "command": python_exe,
            "args": ["-m", "ultron.cli", "mcp"],
            "env": {
                "PYTHONPATH": repo_root,
                "PYTHONUNBUFFERED": "1"
            }
        }
        CLAUDE_JSON_FILE.write_text(json.dumps(claude_cfg, indent=2), encoding="utf-8")

    # 4. Update ~/.claude/settings.json
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
    mcp_servers["ultron"] = {
        "command": python_exe,
        "args": ["-m", "ultron.cli", "mcp"],
        "env": {"PYTHONPATH": repo_root, "PYTHONUNBUFFERED": "1"}
    }

    # 5. Install Ultron PostToolUse Hook for Automatic Context Slashing
    hooks_script_dir = CLAUDE_DIR / "scripts" / "hooks"
    hooks_script_dir.mkdir(parents=True, exist_ok=True)
    hook_runner_file = hooks_script_dir / "ultron-post-tool.py"
    hook_runner_code = f'''import sys
import os

repo_path = r"{repo_root}"
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

from ultron.hooks.post_tool_use import run_hook

if __name__ == "__main__":
    run_hook()
'''
    hook_runner_file.write_text(hook_runner_code, encoding="utf-8")

    post_hooks = settings_data.setdefault("hooks", {}).setdefault("PostToolUse", [])
    has_ultron_post = False
    for entry in post_hooks:
        for h in entry.get("hooks", []):
            if "ultron" in h.get("command", ""):
                has_ultron_post = True
                break
    if not has_ultron_post:
        post_hooks.append({
            "matcher": "Bash|Read|Grep",
            "hooks": [
                {
                    "type": "command",
                    "command": f'python "{str(hook_runner_file).replace(os.sep, "/")}"'
                }
            ]
        })

    SETTINGS_FILE.write_text(json.dumps(settings_data, indent=2), encoding="utf-8")
    results["settings_updated"] = True
    results["hook_installed"] = str(hook_runner_file)
    return results
