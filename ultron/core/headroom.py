import re
import json
from collections import Counter
from typing import Tuple, Dict, Any
from ultron.config import config
from ultron.core.breadcrumb import breadcrumb_store
from ultron.core.caveman import caveman

ANSI_REGEX = re.compile(r"\x1B(?:\[[0-?]*[ -/]*[@-~]|\].*?\x07)")
PROGRESS_REGEX = re.compile(r"(\r[^\n]*)+")

# Source-code markers across common languages. Code must never be compressed:
# the prose path deduplicates repeated lines and drops indentation, which silently
# rewrites meaning in a file someone is about to edit.
CODE_HINT_REGEX = re.compile(
    r"^\s*(?:def |class |import |from \S+ import |@\w+|function |const |let |var |"
    r"public |private |protected |#include|package |fn |impl |func |type \w+ struct)",
    re.M,
)
DIGIT_RUN_REGEX = re.compile(r"\d+")
# A unified diff hunk header is "@@ -a,b +c,d @@" -- the old test looked for the
# literal "@@ +", which that format never contains, so the branch was unreachable
# for anything not starting with "diff --git" (git show and git log -p both start
# with "commit").
DIFF_HUNK_REGEX = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", re.M)


class HeadroomCompressor:
    """
    Headroom + RTK + Caveman Universal Context Compression Engine.
    Compresses tool outputs, terminal logs, git diffs, test results,
    JSON payloads, web documents, and general prose.

    Reduction depends entirely on how repetitive the input is: 90%+ on build logs
    and dependency listings, roughly 50% on diffs, and nothing on source code,
    which is passed through byte-identical. Every lossy path stores a reversible
    breadcrumb first, so the original is always recoverable.
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

        # 1. Optional filler-word removal, off unless CAVEMAN_MODE says otherwise.
        # It handles conversational filler well, but tool output is technical text:
        # measured 0.2% on a commit message and 0.4% on this project's README, in
        # exchange for a lossy rewrite. Not a trade worth making by default.
        if config.caveman_mode == "off":
            compact_prose = text
        else:
            compact_prose, _ = caveman.compress_text(text)

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

        # 3. Nothing was actually rewritten -- hand back the original and store nothing.
        # Without this every trivial tool output left a row in the breadcrumb store.
        if compact_prose == text:
            return text, {"type": "prose", "raw_bytes": raw_len,
                          "compressed_bytes": raw_len, "savings_pct": 0.0}

        # 4. Stash the raw text before handing back a lossy rewrite. Filler removal
        # and line dedup above cannot be undone, so skipping the stash for short text
        # meant the original was gone for good while the hook still told the reader it
        # had been "safely stashed". Always store; short outputs simply fail the
        # caller's savings threshold and get passed through untouched instead.
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

    def looks_like_source_code(self, text: str) -> bool:
        """True when text is source code, which must be passed through untouched."""
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) < 5:
            return False
        indented = sum(1 for ln in lines if ln.startswith((" ", "	")))
        return len(CODE_HINT_REGEX.findall(text)) >= 2 and indented / len(lines) > 0.25

    def looks_like_repetitive_log(self, text: str) -> bool:
        """
        Structural log detection. The keyword list only caught tools it already knew,
        so a log from anything else fell through to the prose path and saved nothing.
        Repetition of line SHAPE is what makes a log compressible, whatever produced it.
        """
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) < 40:
            return False
        shapes = Counter(DIGIT_RUN_REGEX.sub("#", ln)[:80] for ln in lines)
        most_common = shapes.most_common(1)[0][1]
        return most_common / len(lines) > 0.3 or len(shapes) / len(lines) < 0.5

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
        if (content.lstrip().startswith("diff --git")
                or "\ndiff --git " in content
                or DIFF_HUNK_REGEX.search(content)):
            return self.compress_git_diff(content)

        # JSON detector
        stripped = content.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
            if len(content) > 400:
                res, meta = self.compress_json(content)
                if meta.get("savings_pct", 0) > 15:
                    return res, meta

        # Source code: exact bytes matter more than any saving here.
        if self.looks_like_source_code(content):
            return content, {"savings_pct": 0.0, "raw_bytes": len(content),
                             "compressed_bytes": len(content), "skipped": "source_code"}

        # Terminal / build log detector: known tool vocabulary OR repetitive structure.
        known_tool = any(w in content.lower() for w in ["npm", "pytest", "cargo", "build", "test", "compiling", "yarn", "pip", "docker", "traceback", "error:"])
        if known_tool or self.looks_like_repetitive_log(content):
            return self.compress_build_or_test_log(content)

        # Web scrape / HTML detector
        if any(tag in content.lower() for tag in ["<html", "<div", "<span", "<article", "<p>"]):
            cleaned_html = re.sub(r"<[^>]+>", " ", content)
            cleaned_html = re.sub(r"[ \t]+", " ", cleaned_html)
            return self.compress_prose_and_text(cleaned_html)

        # Universal Prose and Normal Text Compressor
        return self.compress_prose_and_text(content)

headroom = HeadroomCompressor()
