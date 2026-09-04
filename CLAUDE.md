# Ultron: In-Process Context Pruner & SQLite Breadcrumb Store

This repository contains Ultron, a high-performance context pruner, reversible SQLite breadcrumb store, and Karpathy workflow engine for Claude Code.

## Architecture & Commands
- `/ultron status` or `python -m ultron.cli status`: Check live token savings and stashed breadcrumbs in SQLite (`~/.ultron/memory.db`).
- `/ultron expand <hash>` or `python -m ultron.cli expand <hash>`: Recover 100% exact raw output from any `[ultron:ref:hash:NL:NB]` breadcrumb tag.
- `/ultron compress <target>` or `python -m ultron.cli compress <target>`: Manually prune a large log, diff, or JSON payload.
- `/karpathy-guidelines`: Enforce Andrej Karpathy's 4 core engineering rules.

## Hooks
- Native `PostToolUse` hook (`ultron/hooks/post_tool_use.py`) automatically intercepts heavy `Bash`, `Read`, and `Grep` outputs. Reduction is 50%–95% on repetitive logs, test runs, and diffs, while source code passes through byte-identical.
