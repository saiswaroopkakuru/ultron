---
name: strategic-compact
description: Suggests strategic context compaction at logical task boundaries instead of arbitrary mid-task auto-compaction.
license: MIT
---

# Strategic Compaction Skill

Suggests manual `/compact` at strategic workflow boundaries rather than suffering arbitrary auto-compaction mid-task.

## Strategic Compaction Boundaries
1. **After Exploration, Before Execution**: Compact research context, keep the finalized implementation plan.
2. **After Completing a Major Milestone**: Fresh start for the next feature phase.
3. **Before Major Context Shifts**: Clear deep debugging context before starting an unrelated task.

## Rules
- Do NOT compact mid-implementation (preserves active working memory).
- Do NOT compact while debugging an unresolved error.
- Keep session checkpoints via Ultron ClaudeMem (`/preserve`) before compacting.
