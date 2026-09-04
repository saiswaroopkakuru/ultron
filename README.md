# ⚡ Ultron: In-Process Context Pruner & SQLite Breadcrumb Store for Claude Code

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License"></a>
  <a href="https://modelcontextprotocol.io/"><img src="https://img.shields.io/badge/MCP-1.27%20Compliant-purple?style=flat-square" alt="MCP"></a>
  <a href="https://anthropic.com"><img src="https://img.shields.io/badge/Claude%20Code-PostToolUse%20Hook-black?style=flat-square" alt="Claude Code"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square" alt="Python">
</p>

<p align="center">
  <strong>Prunes massive tool outputs before they enter the model's context window, keeping the byte-exact original safely stashed in a local SQLite breadcrumb store.</strong>
</p>

---

## 🎯 The Problem

When developing with AI coding agents like **Claude Code**, context windows fill up quickly:
- **Build & Test Outputs**: Running `webpack`, `pytest`, `cargo test`, or `npm test` can dump 5,000–30,000 tokens of repetitive module lines and compiler spam into the context window.
- **Large Git Diffs**: Inspecting a multi-file diff or patch injects hundreds of unchanged context lines.
- **Context Eviction / Token Costs**: Bloated context slows down model generation, increases API costs, and pushes earlier conversation instructions out of active memory.

Existing tools operate either at the **network proxy layer** (requiring TLS certificates and local port routing) or attempt to compress **model output** (prose).

---

## 💎 The Ultron Solution

Ultron operates **directly at the in-process tool boundary** via Claude Code's native `PostToolUse` hook:

1. **Zero Proxy Latency**: No local HTTP proxies or network redirects. The hook intercepts tool results (`Bash`, `Read`, `Grep`, MCP) right before Claude Code serializes them into context.
2. **Deterministic Context Pruning**:
   - **Logs**: Strips ANSI escape codes and progress bars; preserves compiler errors, tracebacks, and summary outcomes while collapsing module compilation spam.
   - **Git Diffs**: Collapses long runs of unchanged context lines (`[... N unchanged lines ...]`), while keeping all hunks (`@@`) and added/removed lines.
   - **JSON**: Prunes repetitive array elements and deeply nested objects.
3. **Reversible Breadcrumbs**: Full uncompressed tool outputs are stored in a local SQLite database (`~/.ultron/memory.db`) with content-addressed SHA-256 hashes (`[ultron:ref:hash:NL:NB]`).
4. **100% Byte-Exact Recovery**: If Claude or the developer needs to inspect the full uncompressed log, `/ultron expand <hash>` or MCP tool `ultron_expand_breadcrumb` instantly restores the original text.
5. **Context-Aware Plugin Router & Skill Dispatcher**: Inspects incoming queries, codebase state, and tool outputs to dynamically orchestrate:
   - **Headroom / Pruner**: Heavy tool outputs, logs, diffs, JSON payloads.
   - **Caveman**: Model output generation (direct, high density, zero filler, byte-exact entities).
   - **Claude-Mem**: Past session history, architectural decisions, and bug history.
   - **Andrej Karpathy Guidelines**: Code modifications, refactors, and feature design.
   - **Claude Skills**: Dynamically dispatches to `tdd-workflow`, `verification-loop`, `strategic-compact`, `security-guardrails`, and `graphify`.

---

## 🤝 Ecosystem Harmony & Plugin Routing

Ultron acts as the intelligent conductor for your Claude Code environment, routing tasks to the right specialized engine based on context:

| System | Role | Layer | Dynamic Trigger Condition |
| :--- | :--- | :--- | :--- |
| **`Ultron Pruner`** | Tool output pruner & breadcrumb store | Tool input context | Terminal build logs, test runs, diffs >120B |
| **`caveman`** | High-density model output compression | Assistant output | Conversational explanations, planning, prose |
| **`claude-mem`** | Cross-session memory & vector retrieval | Session history | Queries asking about past decisions, history, bugs |
| **`Karpathy Guidelines`**| Code simplicity & surgical changes | Code engineering | Implementing features, creating classes, refactors |
| **`Claude Skills`** | Specialized workflow skills | Dynamic execution | TDD on test failures, verification loop before PR |


---

## 🚀 Quick Start

### 1. Installation
```powershell
git clone https://github.com/saiswaroopkakuru/ultron.git
cd ultron
pip install -e .
```

### 2. Configure Claude Code
```powershell
python -m ultron.cli install
```
This automatically configures:
- The `PostToolUse` hook in `~/.claude/settings.json`
- The `ultron` MCP server in `~/.claude.json`
- The `/ultron` skill in `~/.claude/skills/ultron/SKILL.md`

---

## 🛠️ CLI Usage

```powershell
# Check live pruned token metrics & stored breadcrumbs
python -m ultron.cli status

# Losslessly expand any stashed breadcrumb hash
python -m ultron.cli expand effbe51a

# Manually prune a large log or diff
python -m ultron.cli compress build.log

# Purge breadcrumbs older than 7 days
python -m ultron.cli clean --days 7
```

---

## 🔌 MCP Server Tools

When registered with Claude Code or Cursor, Ultron provides:
- `ultron_compress_tool_output(content)`: Prunes raw text and returns the breadcrumb tag.
- `ultron_expand_breadcrumb(hash)`: Losslessly recovers raw text from SQLite.
- `ultron_get_status()`: Returns live telemetry and storage metrics.
- `ultron_karpathy_review(diff_or_code)`: Reviews code against Karpathy's 4 core guidelines.
- `ultron_strategic_compact_check(tool_invocations)`: Recommends `/compact` at milestone boundaries.

---

## 🧪 Testing

Run the test suite:
```powershell
python -m pytest tests/test_core.py -v
```

---

## 📄 License
MIT License. Created by Sai Swaroop Kakuru.
