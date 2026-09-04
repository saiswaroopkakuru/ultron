import re
import json
from collections import Counter
from typing import Tuple, Dict, Any
from ultron.core.breadcrumb import breadcrumb_store

# Source-code markers across common languages. Code must never be pruned: the
# document path deduplicates repeated lines and drops indentation, so a reader
# is shown code that differs from what is on disk.
CODE_HINT_REGEX = re.compile(
    r"^\s*(?:def |class |import |from \S+ import |@\w+|function |const |let |var |"
    r"public |private |protected |#include|package |fn |impl |func |type \w+ struct)",
    re.M,
)
DIGIT_RUN_REGEX = re.compile(r"\d+")
# A real diff carries this marker at the start of a line. Matching it anywhere
# also caught source files that merely quote it, sending code down the diff path.
DIFF_HEADER_REGEX = re.compile(r"^diff --git ", re.M)

ANSI_REGEX = re.compile(r"\x1B(?:\[[0-?]*[ -/]*[@-~]|\].*?\x07)")
PROGRESS_REGEX = re.compile(r"(\r[^\n]*)+")

class PrunerEngine:
    """
    Ultron Context Pruner Engine.
    Prunes tool outputs, terminal logs, git diffs, test results, JSON payloads,
    and large documents before LLM context ingestion, stashing byte-exact
    originals into SQLite breadcrumbs for lossless recovery.

    Reduction tracks how repetitive the input is: on the benchmark fixtures, 93%
    on build logs, 89% on diffs, 99% on JSON, and none on source code, which is
    passed through byte-identical.
    """
    def __init__(self, max_log_lines: int = 35, store=None):
        self.max_log_lines = max_log_lines
        # Injectable so benchmarks and tests can write to a throwaway DB instead
        # of the user's live telemetry. Defaults to the process-wide store.
        self.store = store or breadcrumb_store

    def clean_terminal_noise(self, text: str) -> str:
        """Strips ANSI colors, terminal escapes, and carriage return progress loops."""
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

    def prune_git_diff(self, diff_text: str) -> Tuple[str, Dict[str, Any]]:
        """
        Prunes git diff payloads by collapsing long runs of unmodified context lines (>3 lines),
        while keeping all diff hunk headers (@@), file headers, and +/- additions and deletions.
        """
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
        _, tag = self.store.store(diff_text, content_type="git_diff")
        
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

    def prune_build_or_test_log(self, log_text: str) -> Tuple[str, Dict[str, Any]]:
        """
        Prunes build and test logs (npm, pytest, cargo, webpack, gradle).
        Preserves root commands, fatal errors, tracebacks, and summary outcomes,
        collapsing repetitive module compilation spam.
        """
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
                if len(error_blocks) > 30 and not line.startswith(" ") and not line.startswith("\t"):
                    in_traceback = False

            if i < 5 or any(k in lower for k in ["running", "compiling", "building", "target:"]):
                critical_lines.append(line)

        _, tag = self.store.store(log_text, content_type="build_log")

        output_parts = [
            f"{tag} [ULTRON: Pruned {len(lines)} lines -> {len(critical_lines) + len(error_blocks) + len(summary_lines)} lines]",
            "--- Command / Startup ---",
            "\n".join(critical_lines[:5]),
        ]

        if error_blocks:
            output_parts.extend([
                "--- Failure / Error Details ---",
                "\n".join(error_blocks[:40])
            ])
        else:
            output_parts.append("--- No fatal errors detected ---")

        if summary_lines:
            output_parts.extend([
                "--- Outcome / Summary ---",
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

    def prune_json(self, json_text: str) -> Tuple[str, Dict[str, Any]]:
        """Prunes large JSON payloads by trimming repetitive list elements and nested structures."""
        raw_len = len(json_text)
        try:
            data = json.loads(json_text)
            _, tag = self.store.store(json_text, content_type="json")

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

    def prune_document_text(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """
        Prunes large text documents, articles, or scrape dumps by removing repetitive lines
        and stashing the full text in SQLite breadcrumbs if > 700 bytes.
        """
        raw_len = len(text)
        if raw_len < 200:
            return text, {"savings_pct": 0.0, "raw_bytes": raw_len, "compressed_bytes": raw_len}

        lines = text.splitlines()
        seen = set()
        deduped = []
        for line in lines:
            stripped = line.strip()
            if stripped and len(stripped) > 20:
                if stripped in seen:
                    continue
                seen.add(stripped)
            deduped.append(line)

        compact_text = "\n".join(deduped)

        if raw_len > 700:
            _, tag = self.store.store(text, content_type="text_document")
            result = f"{tag} [ULTRON: Condensed {raw_len:,}B -> {len(compact_text):,}B]\n{compact_text}"
            comp_len = len(result)
            savings_pct = max(0.0, (raw_len - comp_len) / raw_len * 100) if raw_len > 0 else 0.0
            return result, {
                "type": "text_document",
                "raw_bytes": raw_len,
                "compressed_bytes": comp_len,
                "savings_pct": savings_pct,
                "breadcrumb": tag
            }

        comp_len = len(compact_text)
        savings_pct = max(0.0, (raw_len - comp_len) / raw_len * 100) if raw_len > 0 else 0.0
        return compact_text, {
            "type": "text_document",
            "raw_bytes": raw_len,
            "compressed_bytes": comp_len,
            "savings_pct": savings_pct
        }

    def looks_like_source_code(self, text: str) -> bool:
        """True when text is source code, which must be passed through untouched."""
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) < 5:
            return False
        indented = sum(1 for ln in lines if ln.startswith((" ", "\t")))
        return len(CODE_HINT_REGEX.findall(text)) >= 2 and indented / len(lines) > 0.25

    def looks_like_repetitive_log(self, text: str) -> bool:
        """
        Structural log detection. The keyword list only catches tools it already
        knows, so a log from anything else falls through to the document path and
        saves nothing. Repetition of line SHAPE is what makes a log prunable,
        whatever produced it.
        """
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) < 40:
            return False
        shapes = Counter(DIGIT_RUN_REGEX.sub("#", ln)[:80] for ln in lines)
        return shapes.most_common(1)[0][1] / len(lines) > 0.3 or len(shapes) / len(lines) < 0.5

    def prune_tool_output(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """Universal router that inspects tool output content and routes to the best pruner."""
        if not text or len(text) < 120:
            size = len(text) if text else 0
            return text, {"savings_pct": 0.0, "raw_bytes": size, "compressed_bytes": size}

        # Git diffs
        if DIFF_HEADER_REGEX.search(text) or (text.startswith("--- ") and "\n+++ " in text):
            res, meta = self.prune_git_diff(text)
        elif (text.strip().startswith("{") and text.strip().endswith("}")) or (text.strip().startswith("[") and text.strip().endswith("]")):
            try:
                json.loads(text.strip())
                res, meta = self.prune_json(text.strip())
            except Exception:
                res, meta = self.prune_document_text(text)
        elif self.looks_like_source_code(text):
            # Exact bytes matter more than any saving here.
            res, meta = text, {"savings_pct": 0.0, "raw_bytes": len(text),
                               "compressed_bytes": len(text), "skipped": "source_code"}
        elif (any(k in text.lower() for k in ["npm", "yarn", "pnpm", "webpack", "vite", "pytest", "cargo", "gradle", "traceback (", "error:"])
                or self.looks_like_repetitive_log(text)):
            res, meta = self.prune_build_or_test_log(text)
        else:
            res, meta = self.prune_document_text(text)

        if meta.get("savings_pct", 0.0) > 0:
            try:
                self.store.record_savings(meta["raw_bytes"], meta["compressed_bytes"])
            except Exception:
                pass

        return res, meta

    # Backwards compatibility alias
    compress_tool_output = prune_tool_output
    compress_git_diff = prune_git_diff
    compress_build_or_test_log = prune_build_or_test_log
    compress_json = prune_json
    compress_prose_and_text = prune_document_text

pruner = PrunerEngine()
headroom = pruner  # Backward compatibility alias

