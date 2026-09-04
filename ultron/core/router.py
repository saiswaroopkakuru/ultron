import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

CLAUDE_DIR = Path(os.path.expanduser("~/.claude"))
SKILLS_DIR = CLAUDE_DIR / "skills"

class ContextRouter:
    """
    Ultron Context-Aware Plugin Router & Skill Dispatcher.
    Inspects user queries, codebase state, and tool outputs, and dynamically
    orchestrates Headroom (pruner), Caveman (density), Claude-Mem (retrieval),
    Andrej Karpathy guidelines, and specialized Claude skills.
    Enhanced with CL4R1T4S frontier agent scaffolding (Anthropic Concise Mode,
    Claude 3.7 tool budgeting, Factory Intent Gating, Cursor anti-looping, Devin root-cause).
    """
    def __init__(self):
        self._skills_cache: Optional[List[str]] = None

    def discover_installed_skills(self) -> List[str]:
        """Discovers all installed Claude skills in ~/.claude/skills/."""
        if self._skills_cache is not None:
            return self._skills_cache

        skills = []
        if SKILLS_DIR.exists():
            for item in SKILLS_DIR.iterdir():
                if item.is_dir() and (item / "SKILL.md").exists():
                    skills.append(item.name)
        self._skills_cache = sorted(skills)
        return self._skills_cache

    def get_plugin_status(self) -> Dict[str, Any]:
        """Returns the status of all ecosystem tools on this machine."""
        skills = self.discover_installed_skills()
        return {
            "headroom_pruner": {
                "name": "Headroom / Pruner",
                "role": "Tool output & terminal log compression with SQLite breadcrumbs",
                "status": "active_in_process",
                "layer": "input_context"
            },
            "caveman": {
                "name": "Caveman",
                "role": "Model output conciseness & zero-fluff telegraphic brevity",
                "status": "active" if "caveman" in skills else "installed",
                "layer": "model_output"
            },
            "claude_mem": {
                "name": "Claude-Mem",
                "role": "Cross-session memory & Chroma vector / FTS5 retrieval",
                "status": "active_system",
                "layer": "cross_session_memory"
            },
            "karpathy_guidelines": {
                "name": "Andrej Karpathy Guidelines",
                "role": "Code simplicity, surgical changes, and anti-bloat guardrails",
                "status": "active" if "karpathy-guidelines" in skills else "integrated",
                "layer": "code_engineering"
            },
            "claude_skills": {
                "available": skills,
                "count": len(skills)
            }
        }

    def classify_intent(self, text: str) -> str:
        """
        Factory Droid Phase 0 Intent Gate:
        Separates DIAGNOSTIC (read-only inspection/explanation) from
        IMPLEMENTATION (active code mutation, environment changes).
        """
        text_lower = text.lower()
        impl_verbs = [
            "fix", "implement", "add", "refactor", "create", "write", "update",
            "modify", "delete", "replace", "install", "commit", "push", "make pr"
        ]
        diagnostic_verbs = [
            "explain", "what is", "why does", "how does", "where is", "find",
            "show", "inspect", "audit", "analyze", "review", "check", "compare"
        ]
        
        has_impl = any(re.search(rf"\b{re.escape(w)}\b", text_lower) for w in impl_verbs)
        has_diag = any(re.search(rf"\b{re.escape(w)}\b", text_lower) for w in diagnostic_verbs)

        if has_impl and not (has_diag and not any(w in text_lower for w in ["fix", "implement", "add", "modify"])):
            return "IMPLEMENTATION"
        return "DIAGNOSTIC"

    def classify_complexity(self, text: str, length: int) -> Dict[str, Any]:
        """
        Claude 3.7 Sonnet Tool Budgeting & Complexity Classification:
        Categorizes query into Single-Shot, Deep Research, Surgical Edit, or Milestone.
        """
        text_lower = text.lower()
        if any(w in text_lower for w in ["git commit", "create pr", "ready to push", "finished changes", "compact"]):
            return {
                "category": "MILESTONE_GATE",
                "tool_budget": 2,
                "rule": "Verify build & tests, summarize changes, prompt milestone compaction if context is deep."
            }
        
        research_triggers = ["investigate", "explore", "architecture", "deep dive", "audit codebase", "map dependencies", "trace"]
        if any(w in text_lower for w in research_triggers):
            return {
                "category": "DEEP_RESEARCH",
                "tool_budget": 8,
                "rule": "Plan research path first. Batch speculative reads. Synthesize findings before taking action."
            }

        edit_triggers = ["fix", "refactor", "implement", "patch", "edit", "add feature", "rewrite"]
        if any(w in text_lower for w in edit_triggers):
            return {
                "category": "SURGICAL_EDIT",
                "tool_budget": 5,
                "rule": "Read before write. Combine changes into single-pass edits. Enforce 3-strike linter rule."
            }

        return {
            "category": "SINGLE_SHOT_FACTUAL",
            "tool_budget": 1,
            "rule": "Direct answer. Use at most 1 tool call if needed, otherwise respond without calling tools."
        }

    def route_context(self, text: str, communication_mode: str = "concise") -> Dict[str, Any]:
        """
        Analyzes a prompt, codebase context, or tool output and returns
        the optimal plugin and skill routing decision.
        """
        text_lower = text.lower()
        active_plugins = []
        recommended_skills = []
        action_directives = []

        installed = self.discover_installed_skills()
        intent = self.classify_intent(text)
        complexity = self.classify_complexity(text, len(text))

        # 0. Intent & Complexity Directives (CL4R1T4S Factory & Claude 3.7)
        if intent == "DIAGNOSTIC":
            action_directives.append(
                "Intent Gate [DIAGNOSTIC]: Read-only evidence mode. Do NOT modify files or install packages."
            )
        else:
            action_directives.append(
                "Intent Gate [IMPLEMENTATION]: Ensure test/build baseline passes before and after file changes."
            )
        
        action_directives.append(
            f"Complexity [{complexity['category']}]: Budget <= {complexity['tool_budget']} tools. {complexity['rule']}"
        )

        # 1. Check for Cross-Session Memory intent (claude-mem / Windsurf persistence)
        memory_triggers = [
            "how did we", "last time", "earlier session", "previous bug",
            "past decision", "architecture choice", "what did we configure",
            "recall", "remember", "project convention", "why did we"
        ]
        if any(trig in text_lower for trig in memory_triggers):
            active_plugins.append("claude_mem")
            action_directives.append(
                "Memory Intent Detected: Query claude-mem or session history before generating new code."
            )

        # 2. Check for Heavy Tool / Log / Pruning domain (headroom / pruner / Devin disk truncation)
        prune_triggers = [
            "diff --git", "webpack", "npm err", "traceback (most recent",
            "pytest", "cargo build", "error:", "syntaxerror", "compiling module"
        ]
        if any(trig in text_lower for trig in prune_triggers) or len(text) > 800:
            active_plugins.append("headroom_pruner")
            action_directives.append(
                "Heavy Context Detected: Use Ultron Pruner to collapse noise and stash breadcrumbs in SQLite."
            )

        # 3. Check for Code Engineering / Refactoring (Karpathy Guidelines + Cursor/Devin Rules)
        code_triggers = [
            "refactor", "implement", "add feature", "create class", "rewrite",
            "optimize function", "architecture", "redesign", "bugfix", "def ", "class "
        ]
        if any(trig in text_lower for trig in code_triggers) or intent == "IMPLEMENTATION":
            active_plugins.append("karpathy_guidelines")
            action_directives.append(
                "Karpathy Engineering Active: 1. Simplicity first, 2. Surgical changes, 3. Goal-driven testing."
            )
            action_directives.append(
                "Cursor/Devin Guardrail: Zero unrequested comments in code. Max 3 retries on linter errors. Single-pass edits."
            )

        # 4. Check for Specialized Claude Skills
        # A. TDD Workflow & Devin Test Protection
        if any(w in text_lower for w in ["test fail", "assertionerror", "unit test", "tdd", "write tests"]):
            if "tdd-workflow" in installed:
                recommended_skills.append("tdd-workflow")
                action_directives.append("Test Activity: Engage 'tdd-workflow'. Devin Rule: Never alter tests to force pass; fix root cause.")

        # B. Verification Loop
        if any(w in text_lower for w in ["git commit", "create pr", "ready to push", "finished changes", "verify before pr"]):
            if "verification-loop" in installed:
                recommended_skills.append("verification-loop")
                action_directives.append("Delivery Gate: Run 'verification-loop' skill (Build, Types, Lints, Tests, Security).")

        # C. Strategic Compact
        if any(w in text_lower for w in ["compact", "context getting full", "long task", "milestone reached"]):
            if "strategic-compact" in installed:
                recommended_skills.append("strategic-compact")
                action_directives.append("Milestone Boundary: Recommend '/compact' via 'strategic-compact' skill.")

        # D. Security Guardrails
        if any(w in text_lower for w in [".env", "api_key", "secret", "credentials", "token", "password"]):
            if "security-guardrails" in installed:
                recommended_skills.append("security-guardrails")
                action_directives.append("Sensitive Data: Enforce 'security-guardrails' skill (never commit or expose secrets).")

        # E. Graphify
        if any(w in text_lower for w in ["codebase map", "graph dependencies", "architecture diagram", "visualize repo"]):
            if "graphify" in installed:
                recommended_skills.append("graphify")
                action_directives.append("Architecture Map: Summon 'graphify' skill for dependency visualization.")

        # 5. Output Density Protocol (Anthropic Concise Mode vs Caveman)
        if communication_mode == "caveman":
            active_plugins.append("caveman")
            action_directives.append("Density Directive: Use Caveman brevity (direct, zero-filler, 100% byte-exact code & entities).")
        else:
            action_directives.append(
                "Anthropic Concise Mode: Minimize output tokens without preamble/postamble. Keep code 100% complete and working."
            )

        primary_plugin = active_plugins[0] if active_plugins else "karpathy_guidelines"

        return {
            "intent": intent,
            "complexity": complexity["category"],
            "tool_budget": complexity["tool_budget"],
            "primary_plugin": primary_plugin,
            "active_plugins": list(dict.fromkeys(active_plugins)),
            "recommended_skills": list(dict.fromkeys(recommended_skills)),
            "directives": action_directives,
            "summary": (
                f"Intent: {intent} ({complexity['category']}) | "
                f"Active: {', '.join(active_plugins) if active_plugins else 'lean'} | "
                f"Skills: {', '.join(recommended_skills) if recommended_skills else 'standard'} | "
                f"Protocol: {communication_mode.upper()} + Karpathy/Cursor precision"
            )
        }

router = ContextRouter()

