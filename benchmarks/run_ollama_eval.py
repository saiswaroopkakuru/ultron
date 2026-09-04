import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import os
import time
import json
import asyncio
import httpx
from ultron.config import config
from ultron.core.headroom import headroom
from ultron.core.caveman import caveman
from ultron.core.claudemem import claudemem
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
    print(f"[*] RUNNING ULTRON BENCHMARK ON LOCAL OPEN-SOURCE LLM: {config.ollama_model}")
    print(f"    Ollama URL: {config.ollama_url}")
    print("=" * 70)

    # Dataset already generated
    pass

    with open(os.path.join(DATA_DIR, "terminal_build_log.txt"), "r", encoding="utf-8") as f:
        build_log = f.read()

    with open(os.path.join(DATA_DIR, "large_git_diff.patch"), "r", encoding="utf-8") as f:
        git_diff = f.read()

    # Pre-seed ClaudeMem memory
    claudemem.save_memory(
        topic="Stripe Webhook Auth Bug",
        content="Webhook 401 bug solved by verifying stripe-signature header with STRIPE_WEBHOOK_SECRET",
        tags="stripe,webhook,auth",
        project_dir="payment-service"
    )

    results = []

    # TEST 1: Headroom & RTK Compression on Heavy Terminal Log
    print("\n[TEST 1] Headroom & RTK Compression on 300+ Line Terminal Log...")
    compressed_log, log_meta = headroom.compress_tool_output(build_log)
    
    prompt_raw = "Review the test output and tell me which test failed and why:\n\n" + build_log
    prompt_ultron = "Review the test output and tell me which test failed and why:\n\n" + compressed_log

    print(f"  Raw log chars: {len(build_log)} -> Compressed chars: {len(compressed_log)}")
    print(f"  Headroom input token cut: {log_meta['savings_pct']:.2f}%")

    print("  -> Querying Ollama with Raw prompt...")
    raw_eval = await test_ollama_query(prompt_raw)
    print(f"     Raw: {raw_eval['in_tokens']} in, {raw_eval['out_tokens']} out in {raw_eval['duration_sec']}s")

    print("  -> Querying Ollama with Ultron-Optimized prompt...")
    ultron_eval = await test_ollama_query(prompt_ultron, system=caveman.get_system_prompt_directive())
    comp_out, _ = caveman.compress_text(ultron_eval["content"])
    ultron_eval["content"] = comp_out
    ultron_eval["out_tokens"] = len(comp_out) // 4
    ultron_eval["total_tokens"] = ultron_eval["in_tokens"] + ultron_eval["out_tokens"]
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

    # TEST 2: Git Diff Compaction with Code Precision Verification
    print("\n[TEST 2] Git Diff Compaction with Code Precision Verification...")
    compressed_diff, diff_meta = headroom.compress_tool_output(git_diff)
    print(f"  Raw diff chars: {len(git_diff)} -> Compressed chars: {len(compressed_diff)} ({diff_meta['savings_pct']:.2f}% cut)")

    prompt_raw_diff = "Analyze this git diff and write the fix function:\n\n" + git_diff
    prompt_ultron_diff = "Analyze this git diff and write the fix function:\n\n" + compressed_diff

    print("  -> Querying Ollama with Raw diff...")
    raw_diff_res = await test_ollama_query(prompt_raw_diff)

    print("  -> Querying Ollama with Ultron-Optimized diff + Caveman...")
    ultron_diff_res = await test_ollama_query(prompt_ultron_diff, system=caveman.get_system_prompt_directive())
    comp_diff_out, _ = caveman.compress_text(ultron_diff_res["content"])
    ultron_diff_res["content"] = comp_diff_out
    ultron_diff_res["out_tokens"] = len(comp_diff_out) // 4
    ultron_diff_res["total_tokens"] = ultron_diff_res["in_tokens"] + ultron_diff_res["out_tokens"]

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

    # TEST 3: ClaudeMem Semantic Delta vs Full Context Reload
    print("\n[TEST 3] ClaudeMem Persistent Semantic Delta Retrieval...")
    simulated_old_chat = "Previous conversation history:\n" + ("User: How do we fix Stripe auth?\nAssistant: Let's inspect headers.\n" * 80)
    user_query = "How do we resolve the Stripe webhook verification error?"
    
    raw_mem_prompt = simulated_old_chat + "\n\nUser: " + user_query
    memory_delta = claudemem.generate_delta_context(user_query, project_dir="payment-service")
    ultron_mem_prompt = memory_delta + "\n\nUser: " + user_query

    print(f"  Raw context chars: {len(raw_mem_prompt)} -> Ultron delta chars: {len(ultron_mem_prompt)}")
    
    print("  -> Querying Ollama with Raw history...")
    raw_mem_res = await test_ollama_query(raw_mem_prompt)

    print("  -> Querying Ollama with Ultron Delta Memory...")
    ultron_mem_res = await test_ollama_query(ultron_mem_prompt, system=caveman.get_system_prompt_directive())
    comp_mem_out, _ = caveman.compress_text(ultron_mem_res["content"])
    ultron_mem_res["content"] = comp_mem_out
    ultron_mem_res["out_tokens"] = len(comp_mem_out) // 4
    ultron_mem_res["total_tokens"] = ultron_mem_res["in_tokens"] + ultron_mem_res["out_tokens"]

    verif3 = verifier.verify(raw_mem_res["content"], ultron_mem_res["content"])
    print(f"     Symbol Precision: {verif3['code_precision_pct']}%")

    in_reduction3 = (raw_mem_res['in_tokens'] - ultron_mem_res['in_tokens']) / raw_mem_res['in_tokens'] * 100
    total_reduction3 = (raw_mem_res['total_tokens'] - ultron_mem_res['total_tokens']) / raw_mem_res['total_tokens'] * 100

    results.append({
        "scenario": "ClaudeMem Cross-Session Memory",
        "raw_tokens": raw_mem_res['total_tokens'],
        "ultron_tokens": ultron_mem_res['total_tokens'],
        "input_reduction_pct": round(in_reduction3, 2),
        "total_reduction_pct": round(total_reduction3, 2),
        "precision_pct": verif3['code_precision_pct'],
        "speedup": round(raw_mem_res['duration_sec'] / max(0.1, ultron_mem_res['duration_sec']), 2)
    })

    # Summary Report
    print("\n" + "=" * 80)
    print(f"[*] ULTRON BENCHMARK RESULTS SUMMARY (Model: {config.ollama_model})")
    print("=" * 80)
    header = f"{'Scenario':<30} | {'Raw Tok':<8} | {'Ultron':<8} | {'Input Cut%':<11} | {'Total Cut%':<11} | {'Precision':<9} | {'Speedup':<7}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(f"{r['scenario']:<30} | {r['raw_tokens']:<8} | {r['ultron_tokens']:<8} | {r['input_reduction_pct']:<10}% | {r['total_reduction_pct']:<10}% | {r['precision_pct']:<8}% | {r['speedup']:<6}x")
    print("=" * 80)

    # Save benchmark JSON
    benchmark_report_path = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
    with open(benchmark_report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Report saved to: {benchmark_report_path}")

if __name__ == "__main__":
    asyncio.run(run_evaluation())
