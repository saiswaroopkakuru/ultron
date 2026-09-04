---
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
- **`ultron`**: The heavy-data optimizer. Ultron stores raw blobs (diffs, test outputs, compiler traces) out-of-band in SQLite and replaces them with breadcrumbs, cutting prompt token consumption by up to 95%.