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

## 📊 Measured Results

`benchmarks/run_benchmark.py` runs the pruner over four checked-in fixtures. It is
deterministic — no model, no network — so anyone gets these numbers on this commit:

```bash
python benchmarks/run_benchmark.py
```

| Scenario | Raw | Kept | Reduction | Signal kept | Roundtrip |
| :--- | ---: | ---: | ---: | ---: | :--- |
| Build & test log | 21,314 B | 1,561 B | **92.7%** | 100% | byte-exact |
| Git diff | 4,053 B | 443 B | **89.1%** | 100% | byte-exact |
| JSON API response | 29,613 B | 261 B | **99.1%** | 100% | byte-exact |
| Source code (`ultron/core/pruner.py`) | — | — | **0%** | 100% | passed through |

**Signal kept** is the part that matters. Reduction alone proves nothing — deleting
the whole log scores 100%. So each scenario also asserts that the lines carrying the
answer survived: the assertion error, stderr cause and pytest summary for the log;
every `+`/`-` line for the diff; the envelope fields and truncation marker for JSON.
**Roundtrip** re-reads the stashed original out of SQLite and compares it byte-for-byte.

The source-code row reads the pruner's own file, so its size moves with the code; the
assertion that matters there is that input and output are byte-identical.

Reduction tracks how repetitive the input is, so treat these as fixture numbers, not a
promise: a diff that is mostly changed lines, or a log with no repeated section, saves
far less. Source code is never pruned by design.

`benchmarks/run_ollama_eval.py` is a separate optional check that asks a local Ollama
model the same question from raw and pruned input. It needs a running Ollama server and
its numbers move with model sampling, so it is not the headline benchmark.

---

## 🧪 Testing

```bash
python -m pytest tests -v
```

- `tests/test_core.py` — pruner routes, breadcrumb store, telemetry, router, verifier.
- `tests/test_hook_envelope.py` — drives the real `PostToolUse` hook as a subprocess
  over stdin and asserts the replacement still matches Claude Code's tool output
  schemas (`{stdout, stderr, interrupted}` for Bash, `{type, file:{...}}` for Read).
  Claude Code ships often; when that shape drifts the hook stops pruning silently, and
  this file is what turns that into a failing test instead of a quiet regression.

---

## 📄 License
MIT License. Created by Sai Swaroop Kakuru.
