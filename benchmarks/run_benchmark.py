"""
Deterministic pruning benchmark.

Measures what the PostToolUse hook actually does to four kinds of tool output:
a build log, a git diff, a source file, and a JSON payload. No model, no
network, no randomness, so two people running this on the same commit get the
same numbers.

Every scenario reports three things:

  reduction      how much smaller the pruned text is
  signal kept    whether the lines that carry the answer survived pruning
  roundtrip      whether the breadcrumb store returns the original byte-for-byte

A high reduction with a low signal-kept score is a bad result, not a good one.

Usage:
    python benchmarks/run_benchmark.py            # print table, write JSON
    python benchmarks/run_benchmark.py --json     # print JSON only
"""

import json
import os
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = BASE.parent
DATASET = BASE / "dataset"
RESULTS_FILE = BASE / "benchmark_results.json"

# Point the breadcrumb store at a throwaway database before anything imports
# ultron.config, so a benchmark run never touches live telemetry.
_TMP_DIR = tempfile.mkdtemp(prefix="ultron-bench-")
os.environ["ULTRON_DB_PATH"] = str(Path(_TMP_DIR) / "bench.db")

sys.path.insert(0, str(REPO))

from ultron.core.breadcrumb import BreadcrumbStore  # noqa: E402
from ultron.core.pruner import PrunerEngine  # noqa: E402


def count_tokens(text):
    """Token count via tiktoken when installed, else a 4-chars-per-token estimate."""
    try:
        import tiktoken
        return len(tiktoken.get_encoding("cl100k_base").encode(text)), "tiktoken/cl100k_base"
    except Exception:
        return round(len(text) / 4), "estimate(chars/4)"


def load_dataset():
    log_file = DATASET / "terminal_build_log.txt"
    diff_file = DATASET / "large_git_diff.patch"
    if not log_file.exists() or not diff_file.exists():
        sys.path.insert(0, str(DATASET))
        import generate_dataset  # noqa: F401  (writing the files is the import's job)
    return log_file.read_text(encoding="utf-8"), diff_file.read_text(encoding="utf-8")


def build_json_payload():
    """A REST list response of the shape an agent actually pastes into context."""
    return json.dumps({
        "status": "ok",
        "total": 240,
        "items": [
            {"id": i, "sku": f"SKU-{i:04d}", "price": 10 + i, "tags": ["a", "b"]}
            for i in range(240)
        ],
    }, indent=2)


def prose_document():
    """
    Text the router has no rule for, carrying words that used to trigger the log
    pruner by substring. It must come back byte-identical.
    """
    return "\n".join([
        "Quarterly platform review",
        "",
        "The scoring service held its latency budget through the December peak, with one",
        "exception on the 14th traced to a cold cache after a deploy.",
        "Test tooling: pytest for unit and integration suites, load testing before release.",
        "Open question: whether the error: prefix in the legacy parser should be retained.",
    ] * 8)


# Lines that carry the answer. If pruning drops these, the reduction is worthless.
LOG_SIGNALS = [
    "AssertionError: assert 200 == 401",
    "Signature verification failed: Bad HMAC",
    "FAILED tests/test_webhook.py::test_payment_webhook_auth",
    "1 failed, 149 passed",
]


# Envelope fields and the truncation marker that tells the reader rows were dropped.
JSON_SIGNALS = ['"status":"ok"', '"total":240', '"SKU-0000"', "more items"]


def diff_signals(diff_text):
    """Every added and removed line in the diff, which pruning must keep verbatim."""
    return [
        line for line in diff_text.splitlines()
        if (line.startswith("+") or line.startswith("-"))
        and not line.startswith("+++") and not line.startswith("---")
    ]


def signal_score(pruned, signals):
    if not signals:
        return 100.0, []
    missing = [s for s in signals if s not in pruned]
    kept = len(signals) - len(missing)
    return round(kept / len(signals) * 100, 2), missing


def run_scenario(name, raw, pruner, store, signals, expect_passthrough=False):
    pruned, meta = pruner.prune_tool_output(raw)

    raw_tokens, token_method = count_tokens(raw)
    pruned_tokens, _ = count_tokens(pruned)
    reduction = round((len(raw) - len(pruned)) / len(raw) * 100, 2) if raw else 0.0

    kept_pct, missing = signal_score(pruned, signals)

    # Roundtrip: pull the stashed original back out and compare byte-for-byte.
    tag = meta.get("breadcrumb")
    if tag:
        hash_key = tag.split(":")[2]
        roundtrip_exact = store.retrieve(hash_key) == raw
    else:
        roundtrip_exact = pruned == raw  # nothing stashed means nothing was removed

    return {
        "scenario": name,
        "raw_bytes": len(raw),
        "pruned_bytes": len(pruned),
        "raw_tokens": raw_tokens,
        "pruned_tokens": pruned_tokens,
        "token_method": token_method,
        "reduction_pct": reduction,
        "signal_kept_pct": kept_pct,
        "missing_signals": missing,
        "roundtrip_byte_exact": roundtrip_exact,
        "byte_identical_passthrough": pruned == raw,
        "expected_passthrough": expect_passthrough,
        "route": meta.get("type") or meta.get("skipped") or "passthrough",
    }


def main():
    build_log, git_diff = load_dataset()
    source_code = (REPO / "ultron" / "core" / "pruner.py").read_text(encoding="utf-8")
    json_payload = build_json_payload()

    store = BreadcrumbStore(db_path=os.environ["ULTRON_DB_PATH"])
    pruner = PrunerEngine(store=store)

    results = [
        run_scenario("Build & test log", build_log, pruner, store, LOG_SIGNALS),
        run_scenario("Git diff", git_diff, pruner, store, diff_signals(git_diff)),
        run_scenario("Source code (pruner.py)", source_code, pruner, store, [],
                     expect_passthrough=True),
        run_scenario("JSON API response", json_payload, pruner, store, JSON_SIGNALS),
        run_scenario("Prose document", prose_document(), pruner, store, [],
                     expect_passthrough=True),
    ]

    RESULTS_FILE.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    if "--json" in sys.argv:
        print(json.dumps(results, indent=2))
        return 0

    print(f"\nUltron pruning benchmark  (tokens: {results[0]['token_method']})\n")
    header = f"| {'Scenario':<24} | {'Raw tok':>8} | {'Kept tok':>8} | {'Reduction':>9} | {'Signal kept':>11} | {'Roundtrip':>9} |"
    print(header)
    print("|" + "-" * 26 + "|" + "-" * 10 + "|" + "-" * 10 + "|" + "-" * 11 + "|" + "-" * 13 + "|" + "-" * 11 + "|")
    for r in results:
        print(
            f"| {r['scenario']:<24} | {r['raw_tokens']:>8} | {r['pruned_tokens']:>8} | "
            f"{r['reduction_pct']:>8.1f}% | {r['signal_kept_pct']:>10.1f}% | "
            f"{'exact' if r['roundtrip_byte_exact'] else 'FAILED':>9} |"
        )

    print(f"\nWrote {RESULTS_FILE.relative_to(REPO)}")

    failures = [r for r in results if not r["roundtrip_byte_exact"] or r["missing_signals"]]
    for f in failures:
        print(f"  ! {f['scenario']}: missing {f['missing_signals'][:3]}"
              if f["missing_signals"] else f"  ! {f['scenario']}: roundtrip not byte-exact")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
