# Ultron: Context-Aware Plugin Router & In-Process Context Pruner

This repository contains Ultron, an intelligent context router, high-performance context pruner, reversible SQLite breadcrumb store, and Karpathy workflow engine for Claude Code.

## Architecture & Commands
- `/ultron status` or `python -m ultron.cli status`: Check live token savings and stashed breadcrumbs in SQLite (`~/.ultron/memory.db`).
- `/ultron expand <hash>` or `python -m ultron.cli expand <hash>`: Recover 100% exact raw output from any `[ultron:ref:hash:NL:NB]` breadcrumb tag.
- `/ultron compress <target>` or `python -m ultron.cli compress <target>`: Manually prune a large log, diff, or JSON payload.
- `python -m ultron.cli route "<query>"`: Analyze context and determine optimal plugin/skill activation.
- `python -m ultron.cli plugins`: Display discovery status of all installed ecosystem plugins and skills.
- `/karpathy-guidelines`: Enforce Andrej Karpathy's 4 core engineering rules.

## Ecosystem Dynamic Routing
Ultron dynamically inspects context and orchestrates:
- **Headroom / Pruner**: Heavy tool results, build/test logs, diffs, JSON payloads.
- **Caveman**: Model output generation (direct, high density, zero filler, byte-exact entities).
- **Claude-Mem**: Past session history, architectural decisions, and bug history.
- **Andrej Karpathy Guidelines**: Code modifications, refactors, and feature design.
- **Installed Claude Skills**: Dispatches to `tdd-workflow`, `verification-loop`, `strategic-compact`, `security-guardrails`, and `graphify`.

## Hooks
- Native `PostToolUse` hook (`ultron/hooks/post_tool_use.py`) automatically intercepts heavy `Bash`, `Read`, and `Grep` outputs. Reduction is 50%–95% on repetitive logs, test runs, and diffs, while source code passes through byte-identical. Injects contextual skill hints on failures and diffs.
