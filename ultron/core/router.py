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

    def route_context(self, text: str) -> Dict[str, Any]:
        """
        Analyzes a prompt, codebase context, or tool output and returns
        the optimal plugin and skill routing decision.
        """
        text_lower = text.lower()
        active_plugins = []
        recommended_skills = []
        action_directives = []

        installed = self.discover_installed_skills()

        # 1. Check for Cross-Session Memory intent (claude-mem)
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

        # 2. Check for Heavy Tool / Log / Pruning domain (headroom / pruner)
        prune_triggers = [
            "diff --git", "webpack", "npm err", "traceback (most recent",
            "pytest", "cargo build", "error:", "syntaxerror", "compiling module"
        ]
        if any(trig in text_lower for trig in prune_triggers) or len(text) > 800:
            active_plugins.append("headroom_pruner")
            action_directives.append(
                "Heavy Context Detected: Use Ultron Pruner to collapse noise and stash breadcrumbs in SQLite."
            )

        # 3. Check for Code Engineering / Refactoring (Karpathy Guidelines)
        code_triggers = [
            "refactor", "implement", "add feature", "create class", "rewrite",
            "optimize function", "architecture", "redesign", "bugfix", "def ", "class "
        ]
        if any(trig in text_lower for trig in code_triggers):
            active_plugins.append("karpathy_guidelines")
            action_directives.append(
                "Code Change Detected: Apply Karpathy Guidelines (1. Think first, 2. Simplicity, 3. Surgical changes, 4. Goal-driven)."
            )

        # 4. Check for Specialized Claude Skills
        # A. TDD Workflow
        if any(w in text_lower for w in ["test fail", "assertionerror", "unit test", "tdd", "write tests"]):
            if "tdd-workflow" in installed:
                recommended_skills.append("tdd-workflow")
                action_directives.append("Test Activity: Engage 'tdd-workflow' skill (Red -> Green -> Refactor).")

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

        # 5. Output Density Protocol (Caveman)
        # Always prescribe caveman brevity for assistant communication unless code-only
        active_plugins.append("caveman")
        action_directives.append("Communication Directive: Use Caveman density (direct, zero-filler, 100% byte-exact code & entities).")

        primary_plugin = active_plugins[0] if active_plugins else "caveman"

        return {
            "primary_plugin": primary_plugin,
            "active_plugins": list(dict.fromkeys(active_plugins)),
            "recommended_skills": list(dict.fromkeys(recommended_skills)),
            "directives": action_directives,
            "summary": (
                f"Active: {', '.join(active_plugins)} | "
                f"Skills: {', '.join(recommended_skills) if recommended_skills else 'standard'} | "
                f"Protocol: Caveman density + Karpathy precision"
            )
        }

router = ContextRouter()
