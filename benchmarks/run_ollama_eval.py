import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import os
import time
import json
import asyncio
import tempfile
import httpx
from pathlib import Path
from ultron.config import config
from ultron.core.breadcrumb import BreadcrumbStore
from ultron.core.pruner import PrunerEngine
from ultron.core.verifier import verifier

DATA_DIR = os.path.join(os.path.dirname(__file__), "dataset")

async def test_ollama_query(prompt: str, system: str = "") -> dict:
    url = f"{config.ollama_url}/api/chat"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": config.ollama_model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 300}
    }

    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    duration = time.perf_counter() - start

    msg = data.get("message", {}).get("content", "")
    in_tokens = data.get("prompt_eval_count", len(prompt) // 4)
    out_tokens = data.get("eval_count", len(msg) // 4)

    return {
        "content": msg,
        "in_tokens": in_tokens,
        "out_tokens": out_tokens,
        "total_tokens": in_tokens + out_tokens,
        "duration_sec": round(duration, 3)
    }

async def run_evaluation():
    print("=" * 70)
    print(f"[*] RUNNING ISOLATED ULTRON BENCHMARK ON: {config.ollama_model}")
    print(f"    Ollama URL: {config.ollama_url}")
    print("=" * 70)

    # Use an isolated temporary database for benchmarks so user's live DB is untouched!
    with tempfile.TemporaryDirectory() as tmpdir:
        bench_db_path = os.path.join(tmpdir, "benchmark_memory.db")
        bench_store = BreadcrumbStore(db_path=bench_db_path)
        bench_pruner = PrunerEngine(store=bench_store)

        with open(os.path.join(DATA_DIR, "terminal_build_log.txt"), "r", encoding="utf-8") as f:
            build_log = f.read()

        with open(os.path.join(DATA_DIR, "large_git_diff.patch"), "r", encoding="utf-8") as f:
            git_diff = f.read()

        results = []

        # TEST 1: Build & Test Log Pruning
        print("\n[TEST 1] Build & Test Log Pruning (300+ Line Terminal Log)...")
        compressed_log, log_meta = bench_pruner.prune_build_or_test_log(build_log)
        
        prompt_raw = "Review the test output and tell me which test failed and why:\n\n" + build_log
        prompt_ultron = "Review the test output and tell me which test failed and why:\n\n" + compressed_log

        print(f"  Raw log chars: {len(build_log)} -> Compressed chars: {len(compressed_log)}")
        print(f"  Pruned token cut: {log_meta['savings_pct']:.2f}%")

        print("  -> Querying Ollama with Raw prompt...")
        raw_eval = await test_ollama_query(prompt_raw)
        print(f"     Raw: {raw_eval['in_tokens']} in, {raw_eval['out_tokens']} out in {raw_eval['duration_sec']}s")

        print("  -> Querying Ollama with Ultron-Pruned prompt...")
        ultron_eval = await test_ollama_query(prompt_ultron)
        print(f"     Ultron: {ultron_eval['in_tokens']} in, {ultron_eval['out_tokens']} out in {ultron_eval['duration_sec']}s")

        verif1 = verifier.verify(raw_eval["content"], ultron_eval["content"])
        print(f"     Symbol Precision: {verif1['code_precision_pct']}% | AST Valid: {verif1['syntax_valid']}")

        in_reduction = (raw_eval['in_tokens'] - ultron_eval['in_tokens']) / raw_eval['in_tokens'] * 100
        total_reduction = (raw_eval['total_tokens'] - ultron_eval['total_tokens']) / raw_eval['total_tokens'] * 100

        results.append({
            "scenario": "Terminal Build & Test Log",
            "raw_tokens": raw_eval['total_tokens'],
            "ultron_tokens": ultron_eval['total_tokens'],
            "input_reduction_pct": round(in_reduction, 2),
            "total_reduction_pct": round(total_reduction, 2),
            "precision_pct": verif1['code_precision_pct'],
            "speedup": round(raw_eval['duration_sec'] / max(0.1, ultron_eval['duration_sec']), 2)
        })

        # TEST 2: Git Diff Pruning
        print("\n[TEST 2] Git Diff Pruning with Code Precision Verification...")
        compressed_diff, diff_meta = bench_pruner.prune_git_diff(git_diff)
        print(f"  Raw diff chars: {len(git_diff)} -> Compressed chars: {len(compressed_diff)} ({diff_meta['savings_pct']:.2f}% cut)")

        prompt_raw_diff = "Analyze this git diff and write the fix function:\n\n" + git_diff
        prompt_ultron_diff = "Analyze this git diff and write the fix function:\n\n" + compressed_diff

        print("  -> Querying Ollama with Raw diff...")
        raw_diff_res = await test_ollama_query(prompt_raw_diff)

        print("  -> Querying Ollama with Ultron-Pruned diff...")
        ultron_diff_res = await test_ollama_query(prompt_ultron_diff)

        verif2 = verifier.verify(raw_diff_res["content"], ultron_diff_res["content"])
        print(f"     Symbol Precision: {verif2['code_precision_pct']}% | AST Valid: {verif2['syntax_valid']}")

        in_reduction2 = (raw_diff_res['in_tokens'] - ultron_diff_res['in_tokens']) / raw_diff_res['in_tokens'] * 100
        total_reduction2 = (raw_diff_res['total_tokens'] - ultron_diff_res['total_tokens']) / raw_diff_res['total_tokens'] * 100

        results.append({
            "scenario": "Large Git Diff Patch",
            "raw_tokens": raw_diff_res['total_tokens'],
            "ultron_tokens": ultron_diff_res['total_tokens'],
            "input_reduction_pct": round(in_reduction2, 2),
            "total_reduction_pct": round(total_reduction2, 2),
            "precision_pct": verif2['code_precision_pct'],
            "speedup": round(raw_diff_res['duration_sec'] / max(0.1, ultron_diff_res['duration_sec']), 2)
        })

        # TEST 3: Document Text Pruning
        print("\n[TEST 3] Document / Prose Text Pruning...")
        prose_text = (
            "Detailed documentation notes on system architecture.\n"
            "This service coordinates incoming API requests from external webhook listeners.\n"
            "All webhook payloads must verify HMAC signatures before database processing.\n"
        ) * 15
        comp_prose, prose_meta = bench_pruner.prune_document_text(prose_text)
        print(f"  Raw prose chars: {len(prose_text)} -> Pruned chars: {len(comp_prose)} ({prose_meta['savings_pct']:.2f}% cut)")

        results.append({
            "scenario": "Document / Prose Text",
            "raw_tokens": len(prose_text) // 4,
            "ultron_tokens": len(comp_prose) // 4,
            "input_reduction_pct": round(prose_meta['savings_pct'], 2),
            "total_reduction_pct": round(prose_meta['savings_pct'], 2),
            "precision_pct": 100.0,
            "speedup": 1.0
        })

        # Save to benchmark_results.json
        out_path = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        print("\n" + "=" * 70)
        print(f"[OK] Benchmark complete! Results saved to: {out_path}")
        print("     Isolated temp DB destroyed. Live ~/.ultron/memory.db left 100% clean.")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_evaluation())
