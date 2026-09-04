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
description: Reversible tool-output context pruner, SQLite breadcrumb store, and Karpathy coding guidelines. Triggers on /ultron, /ultron status, /ultron expand <hash>, or /ultron compress.
---

# /ultron - Ultron In-Process Context Pruner & Breadcrumb Store

Ultron automatically prunes heavy tool output (terminal logs, pytest/cargo runs, git diffs, JSON)
before it enters the model context, storing the byte-exact original in a local SQLite breadcrumb store.
Reduction tracks how repetitive the input is. On the repo's benchmark fixtures: 93% on
build logs, 89% on git diffs, 99% on JSON, and 0% on source code, which passes untouched.

1. **Reversible Breadcrumbs**: Large outputs are replaced by tags like `[ultron:ref:hash:NL:NB]`. Full raw output is preserved in `~/.ultron/memory.db` and can be expanded on demand with zero loss.
2. **PostToolUse Hook**: Runs natively inside Claude Code's tool execution loop with zero network proxy latency.
3. **Karpathy Coding Guidelines**: Built-in review tools for simplicity, surgical changes, and anti-bloat.

---

## Instructions for the Assistant When Invoked

When the user types `/ultron` or any subcommand, execute the corresponding action immediately:

### 1. `/ultron` or `/ultron status`
Display live token savings and recent breadcrumbs:
- **If Ultron MCP tools are available**: Call `ultron_get_status()`.
- **Otherwise**: Execute:
  ```powershell
  python -m ultron.cli status
  ```

### 2. `/ultron expand <hash>`
Expand a stashed breadcrumb back to its original raw output:
- **If Ultron MCP tools are available**: Call `ultron_expand_breadcrumb(ref_tag_or_hash="<hash>")`.
- **Otherwise**: Execute:
  ```powershell
  python -m ultron.cli expand <hash>
  ```

### 3. `/ultron compress <target>` or `/compress`
Prune a massive log file, diff, or JSON payload:
- **If Ultron MCP tools are available**: Call `ultron_compress_tool_output(content="<text>")`.
- **Otherwise**: Execute:
  ```powershell
  python -m ultron.cli compress "<target>"
  ```

---

## Relationship to Other Tools
- **`claude-mem`**: Dedicated cross-session memory with Chroma vector embeddings + FTS5 full-text indexing.
- **`caveman`**: Model output compression (removes conversational filler from assistant responses).
- **`ultron`**: In-process tool-output context pruner and SQLite breadcrumb store. It shrinks input tokens before context ingestion."""

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

    # 5. Install Ultron Hooks (PreToolUse for Execution Pruning + PostToolUse for Context Guidance)
    hooks_script_dir = CLAUDE_DIR / "scripts" / "hooks"
    hooks_script_dir.mkdir(parents=True, exist_ok=True)
    
    # Pre-tool hook: Rewrites heavy commands to python -m ultron.runner
    pre_hook_file = hooks_script_dir / "ultron-pre-tool.py"
    pre_hook_code = f'''import sys
import os

repo_path = r"{repo_root}"
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

from ultron.hooks.pre_tool_use import run_hook

if __name__ == "__main__":
    run_hook()
'''
    pre_hook_file.write_text(pre_hook_code, encoding="utf-8")

    # Post-tool hook: Injects skill hints and breadcrumb references via additionalContext
    post_hook_file = hooks_script_dir / "ultron-post-tool.py"
    post_hook_code = f'''import sys
import os

repo_path = r"{repo_root}"
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

from ultron.hooks.post_tool_use import run_hook

if __name__ == "__main__":
    run_hook()
'''
    post_hook_file.write_text(post_hook_code, encoding="utf-8")

    # Wire PreToolUse for Bash
    pre_hooks = settings_data.setdefault("hooks", {}).setdefault("PreToolUse", [])
    has_ultron_pre = False
    for entry in pre_hooks:
        for h in entry.get("hooks", []):
            if "ultron" in h.get("command", ""):
                # Update command to use new ultron-pre-tool.py
                h["command"] = f'python "{str(pre_hook_file).replace(os.sep, "/")}"'
                has_ultron_pre = True
                break
    if not has_ultron_pre:
        pre_hooks.append({
            "matcher": "Bash",
            "hooks": [
                {
                    "type": "command",
                    "command": f'python "{str(pre_hook_file).replace(os.sep, "/")}"',
                    "timeout": 10
                }
            ]
        })

    # Wire PostToolUse for Bash|Read|Grep
    post_hooks = settings_data.setdefault("hooks", {}).setdefault("PostToolUse", [])
    has_ultron_post = False
    for entry in post_hooks:
        for h in entry.get("hooks", []):
            if "ultron" in h.get("command", ""):
                h["command"] = f'python "{str(post_hook_file).replace(os.sep, "/")}"'
                has_ultron_post = True
                break
    if not has_ultron_post:
        post_hooks.append({
            "matcher": "Bash|Read|Grep",
            "hooks": [
                {
                    "type": "command",
                    "command": f'python "{str(post_hook_file).replace(os.sep, "/")}"'
                }
            ]
        })

    SETTINGS_FILE.write_text(json.dumps(settings_data, indent=2), encoding="utf-8")
    results["settings_updated"] = True
    results["pre_hook_installed"] = str(pre_hook_file)
    results["post_hook_installed"] = str(post_hook_file)
    return results
