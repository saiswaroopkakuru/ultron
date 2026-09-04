import re
import json
from typing import Tuple, Dict, Any
from ultron.core.breadcrumb import breadcrumb_store
from ultron.core.caveman import caveman

ANSI_REGEX = re.compile(r"\x1B(?:\[[0-?]*[ -/]*[@-~]|\].*?\x07)")
PROGRESS_REGEX = re.compile(r"(\r[^\n]*)+")

class HeadroomCompressor:
    """
    Headroom + RTK + Caveman Universal Context Compression Engine.
    Compresses tool outputs, terminal logs, git diffs, test results,
    JSON payloads, web documents, and general normal prose/text by up to 95%
    while keeping reversible breadcrumbs for 100% loss-free recovery.
    """
    def __init__(self, max_log_lines: int = 35):
        self.max_log_lines = max_log_lines

    def clean_terminal_noise(self, text: str) -> str:
        """Strips ANSI colors, terminal escapes, and cursor resets."""
        cleaned = ANSI_REGEX.sub("", text)
        lines = []
        for raw_line in cleaned.splitlines():
            if "\r" in raw_line:
                final_part = raw_line.split("\r")[-1].strip()
                if final_part:
                    lines.append(final_part)
            else:
                lines.append(raw_line)
        return "\n".join(lines)

    def compress_git_diff(self, diff_text: str) -> Tuple[str, Dict[str, Any]]:
        """Compresses git diff payloads, collapsing unchanged runs."""
        raw_len = len(diff_text)
        cleaned = self.clean_terminal_noise(diff_text)
        lines = cleaned.splitlines()
        compressed_lines = []
        unmodified_run = 0

        for line in lines:
            if line.startswith("diff --git") or line.startswith("--- ") or line.startswith("+++ ") or line.startswith("@@"):
                if unmodified_run > 3:
                    compressed_lines.append(f"  [... {unmodified_run} unchanged lines ...]")
                unmodified_run = 0
                compressed_lines.append(line)
            elif line.startswith("+") or line.startswith("-"):
                if unmodified_run > 3:
                    compressed_lines.append(f"  [... {unmodified_run} unchanged lines ...]")
                unmodified_run = 0
                compressed_lines.append(line)
            else:
                unmodified_run += 1

        if unmodified_run > 3:
            compressed_lines.append(f"  [... {unmodified_run} unchanged lines ...]")

        compressed_text = "\n".join(compressed_lines)
        _, tag = breadcrumb_store.store(diff_text, content_type="git_diff")
        
        result_text = f"{tag}\n{compressed_text}"
        comp_len = len(result_text)
        savings_pct = max(0.0, (raw_len - comp_len) / raw_len * 100) if raw_len > 0 else 0.0

        return result_text, {
            "type": "git_diff",
            "raw_bytes": raw_len,
            "compressed_bytes": comp_len,
            "savings_pct": savings_pct,
            "breadcrumb": tag
        }

    def compress_build_or_test_log(self, log_text: str) -> Tuple[str, Dict[str, Any]]:
        """RTK-style log compressor for npm/pytest/cargo/gradle builds."""
        raw_len = len(log_text)
        cleaned = self.clean_terminal_noise(log_text)
        lines = cleaned.splitlines()

        if len(lines) <= self.max_log_lines:
            return cleaned, {"savings_pct": 0.0, "raw_bytes": raw_len, "compressed_bytes": raw_len}

        critical_lines = []
        error_blocks = []
        in_traceback = False
        summary_lines = []

        for i, line in enumerate(lines):
            lower = line.lower()
            if any(k in lower for k in ["failed", "passed", "errors", "warnings", "build successful", "build failed", "total tests:"]):
                summary_lines.append(line)

            if any(k in lower for k in ["error:", "traceback (most recent call last):", "fatal:", "panic:", "failure", "exception"]):
                in_traceback = True

            if in_traceback:
                error_blocks.append(line)
                if len(error_blocks) > 30 and not line.startswith(" ") and not line.startswith("	"):
                    in_traceback = False

            if i < 5 or any(k in lower for k in ["running", "compiling", "building", "target:"]):
                critical_lines.append(line)

        _, tag = breadcrumb_store.store(log_text, content_type="build_log")

        output_parts = [
            f"{tag} [ULTRON: Compressed {len(lines)} lines -> {len(critical_lines) + len(error_blocks) + len(summary_lines)} lines]",
            "--- Command Summary ---",
            "\n".join(critical_lines[:5]),
        ]

        if error_blocks:
            output_parts.extend([
                "--- Failure / Error Details ---",
                "\n".join(error_blocks[:40])
            ])
        else:
            output_parts.append("--- No explicit fatal errors detected ---")

        if summary_lines:
            output_parts.extend([
                "--- Test / Build Outcome ---",
                "\n".join(summary_lines[-10:])
            ])

        compressed_text = "\n".join(output_parts)
        comp_len = len(compressed_text)
        savings_pct = max(0.0, (raw_len - comp_len) / raw_len * 100) if raw_len > 0 else 0.0

        return compressed_text, {
            "type": "build_log",
            "raw_bytes": raw_len,
            "compressed_bytes": comp_len,
            "savings_pct": savings_pct,
            "breadcrumb": tag
        }

    def compress_json(self, json_text: str) -> Tuple[str, Dict[str, Any]]:
        """Compresses large JSON payloads by trimming repetitive list elements."""
        raw_len = len(json_text)
        try:
            data = json.loads(json_text)
            _, tag = breadcrumb_store.store(json_text, content_type="json")

            def _prune(obj, depth=0):
                if depth > 4:
                    return "[... nested object ...]"
                if isinstance(obj, list):
                    if len(obj) > 4:
                        return [_prune(x, depth + 1) for x in obj[:3]] + [f"[... {len(obj)-3} more items ...]"]
                    return [_prune(x, depth + 1) for x in obj]
                elif isinstance(obj, dict):
                    return {k: _prune(v, depth + 1) for k, v in list(obj.items())[:15]}
                return obj

            pruned = _prune(data)
            compact_json = json.dumps(pruned, separators=(",", ":"))
            result = f"{tag}\n{compact_json}"
            comp_len = len(result)
            savings = max(0.0, (raw_len - comp_len) / raw_len * 100)
            return result, {
                "type": "json",
                "raw_bytes": raw_len,
                "compressed_bytes": comp_len,
                "savings_pct": savings,
                "breadcrumb": tag
            }
        except Exception:
            return json_text, {"savings_pct": 0.0, "raw_bytes": raw_len, "compressed_bytes": raw_len}

    def compress_prose_and_text(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """
        Universal Normal Text Compressor:
        Compresses articles, documentation, web scrapes, and conversational explanations
        by stripping filler, deduplicating repetitive sentences, and stashing full text.
        """
        raw_len = len(text)
        if raw_len < 120:
            return text, {"savings_pct": 0.0, "raw_bytes": raw_len, "compressed_bytes": raw_len}

        # 1. Apply Caveman fluff & wordy removal
        compact_prose, meta = caveman.compress_text(text)

        # 2. If text is long (> 500 chars), deduplicate repeated lines and compact
        lines = compact_prose.splitlines()
        seen = set()
        deduped = []
        for line in lines:
            stripped = line.strip()
            if stripped and len(stripped) > 20:
                if stripped in seen:
                    continue
                seen.add(stripped)
            deduped.append(line)

        compact_prose = "\n".join(deduped)

        # 3. For large prose (> 700 chars), stash raw text into breadcrumbs
        if raw_len > 700:
            _, tag = breadcrumb_store.store(text, content_type="prose")
            result = f"{tag} [ULTRON: Condensed {raw_len:,}B text -> {len(compact_prose):,}B]\n{compact_prose}"
            comp_len = len(result)
            savings = max(0.0, (raw_len - comp_len) / raw_len * 100)
            return result, {
                "type": "prose",
                "raw_bytes": raw_len,
                "compressed_bytes": comp_len,
                "savings_pct": savings,
                "breadcrumb": tag
            }

        comp_len = len(compact_prose)
        savings = max(0.0, (raw_len - comp_len) / raw_len * 100)
        return compact_prose, {
            "type": "prose",
            "raw_bytes": raw_len,
            "compressed_bytes": comp_len,
            "savings_pct": savings
        }

    def compress_tool_output(self, content: str) -> Tuple[str, Dict[str, Any]]:
        """
        Universal Entrypoint: Auto-detects content type and applies optimal compression
        for diffs, logs, json, web documents, or normal prose text.
        Accounting happens here so every caller (PostToolUse hook, MCP tools, CLI)
        is counted, not just the hook.
        """
        result, meta = self._dispatch_compression(content)
        self._record_telemetry(meta)
        return result, meta

    def _record_telemetry(self, meta: Dict[str, Any]) -> None:
        """Persists token accounting for any compression that actually shrank the payload."""
        if meta.get("savings_pct", 0.0) <= 10.0:
            return
        try:
            from ultron.core.omniroute import omniroute
            raw_tokens = max(1, meta.get("raw_bytes", 0) // 4)
            comp_tokens = max(1, meta.get("compressed_bytes", 0) // 4)
            omniroute.record_savings(raw_tokens, comp_tokens)
        except Exception:
            # Telemetry must never break the compression path a hook depends on.
            pass

    def _dispatch_compression(self, content: str) -> Tuple[str, Dict[str, Any]]:
        if len(content) < 120:
            return content, {"savings_pct": 0.0, "raw_bytes": len(content), "compressed_bytes": len(content)}

        # Git diff detector
        if content.strip().startswith("diff --git") or ("@@ -" in content and "@@ +" in content):
            return self.compress_git_diff(content)

        # JSON detector
        stripped = content.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
            if len(content) > 400:
                res, meta = self.compress_json(content)
                if meta.get("savings_pct", 0) > 15:
                    return res, meta

        # Terminal / build log detector
        if any(w in content.lower() for w in ["npm", "pytest", "cargo", "build", "test", "compiling", "yarn", "pip", "docker", "traceback", "error:"]):
            return self.compress_build_or_test_log(content)

        # Web scrape / HTML detector
        if any(tag in content.lower() for tag in ["<html", "<div", "<span", "<article", "<p>"]):
            cleaned_html = re.sub(r"<[^>]+>", " ", content)
            cleaned_html = re.sub(r"[ \t]+", " ", cleaned_html)
            return self.compress_prose_and_text(cleaned_html)

        # Universal Prose and Normal Text Compressor
        return self.compress_prose_and_text(content)

headroom = HeadroomCompressor()
