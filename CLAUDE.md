# Ultron: Unified 95% Token Optimization & Precision Gateway

This repository contains Ultron, an open-source token optimizer, reversible breadcrumb store, and Karpathy workflow engine.

## Architecture & Commands
- `/ultron status` or `ultron status`: Check live token savings, routed requests, and stashed breadcrumbs in SQLite (`~/.ultron/memory.db`).
- `/ultron expand <hash>` or `ultron expand <hash>`: Recover 100% exact raw output from any `[ultron:ref:hash:NL:NB]` breadcrumb tag.
- `/ultron recall <query>`: Search cross-session BM25 memories.
- `/ultron preserve <milestone>`: Checkpoint architectural decisions.
- `/karpathy-guidelines`: Enforce Andrej Karpathy's 4 core engineering rules.

## Hooks
- Native `PostToolUse` hook (`ultron/hooks/post_tool_use.py`) automatically intercepts heavy `Bash`, `Read`, and `Grep` outputs, saving 70% to 95% of prompt tokens without manual intervention.
