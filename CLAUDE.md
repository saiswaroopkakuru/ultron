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
- **Anthropic Concise Mode / Caveman**: Model output generation (direct, high density, zero filler, byte-exact entities).
- **Claude-Mem**: Past session history, architectural decisions, and bug history.
- **Andrej Karpathy Guidelines & CL4R1T4S Frontier Scaffolding**: Code modifications, refactors, and feature design.
- **Installed Claude Skills**: Dispatches to `frontier-scaffold`, `tdd-workflow`, `verification-loop`, `strategic-compact`, `security-guardrails`, and `graphify`.

## Frontier Cognitive Scaffolding (CL4R1T4S)
- **Phase 0 Intent Gate**: Distinguish `DIAGNOSTIC` (read-only evidence, no file edits or installs) from `IMPLEMENTATION`.
- **Query Complexity Budget**: 1 tool call max for factual queries; multi-step planning for deep research; single-pass batched edits for surgical implementation.
- **Zero Code Comments**: Do not pollute generated code with docstrings or inline explanations unless requested (saves 20–35% tokens).
- **3-Strike Loop Breaker**: Never loop more than 3 times on the same error. Stop and isolate root cause.
- **Devin Root-Cause Rule**: Never modify test assertions to force tests to pass; fix the underlying code.

## Hooks & Execution
- Native `PreToolUse` hook rewrites shell executions through cross-platform `ultron.runner` to prune stdout at runtime.
- Native `PostToolUse` hook (`ultron/hooks/post_tool_use.py`) automatically intercepts heavy `Bash`, `Read`, and `Grep` outputs. Pruning runs only on positive identification: a unified diff, valid JSON, or a build/test log matching a runner or log-level line at the start of a line with 40+ lines. Everything else, source code and prose included, passes through byte-identical. On the repo's benchmark fixtures (`python benchmarks/run_benchmark.py`): 93% on build logs, 89% on git diffs, 99% on JSON payloads, 0% on source code and prose. Injects contextual skill hints on failures and diffs.

