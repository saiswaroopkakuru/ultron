import os
import json
import logging
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, Response, StreamingResponse
from ultron.config import config
from ultron.core.headroom import headroom
from ultron.core.caveman import caveman
from ultron.core.claudemem import claudemem
from ultron.core.omniroute import omniroute
from ultron.core.cache_guard import cache_guard
from ultron.core.breadcrumb import breadcrumb_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ultron.proxy")

app = FastAPI(title="Ultron AI Token Optimization Gateway", version="1.0.0")

def compress_request_messages(messages: list) -> tuple:
    """
    Applies Headroom & RTK compression to tool results and past verbose turns.
    """
    raw_char_count = 0
    compressed_char_count = 0
    new_messages = []

    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            new_blocks = []
            for block in content:
                btype = block.get("type")
                if btype == "tool_result":
                    res_content = block.get("content", "")
                    if isinstance(res_content, str):
                        raw_char_count += len(res_content)
                        compressed, meta = headroom.compress_tool_output(res_content)
                        compressed_char_count += len(compressed)
                        new_block = dict(block)
                        new_block["content"] = compressed
                        new_blocks.append(new_block)
                    else:
                        new_blocks.append(block)
                else:
                    new_blocks.append(block)
            new_msg = dict(msg)
            new_msg["content"] = new_blocks
            new_messages.append(new_msg)
        elif isinstance(content, str):
            raw_char_count += len(content)
            # If large user input or assistant turn with noisy logs
            if len(content) > config.min_compress_chars:
                compressed, meta = headroom.compress_tool_output(content)
                compressed_char_count += len(compressed)
                new_msg = dict(msg)
                new_msg["content"] = compressed
                new_messages.append(new_msg)
            else:
                compressed_char_count += len(content)
                new_messages.append(msg)
        else:
            new_messages.append(msg)

    return new_messages, raw_char_count, compressed_char_count

class Tuple_compressed(tuple):
    pass

@app.post("/v1/messages")
async def handle_anthropic_messages(request: Request):
    """
    Anthropic / Claude Code API Proxy Endpoint.
    1. Intercepts incoming messages and applies Headroom compression to tool results.
    2. Injects Caveman directive and ClaudeMem delta context via CacheGuard.
    3. Forwards to upstream Anthropic or falls back to local Ollama.
    4. Post-processes output with Caveman compression.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    raw_messages = body.get("messages", [])
    system_prompt = body.get("system", "")

    # 1. Compress tool results and context (Headroom / RTK)
    optimized_messages, raw_chars, comp_chars = compress_request_messages(raw_messages)
    
    # Estimate token savings (~4 chars per token)
    raw_tokens_est = raw_chars // 4
    comp_tokens_est = comp_chars // 4
    omniroute.record_savings(raw_tokens_est, comp_tokens_est)

    # 2. Retrieve ClaudeMem delta memory based on recent prompt
    last_user_prompt = ""
    for m in reversed(optimized_messages):
        if m.get("role") == "user":
            c = m.get("content")
            if isinstance(c, str):
                last_user_prompt = c
            elif isinstance(c, list):
                last_user_prompt = " ".join([b.get("text", "") for b in c if b.get("type") == "text"])
            break

    memory_delta = claudemem.generate_delta_context(last_user_prompt) if last_user_prompt else ""
    caveman_directive = caveman.get_system_prompt_directive()

    dynamic_injection = "\n\n".join([x for x in [caveman_directive, memory_delta] if x])

    # 3. Stabilize prompt caching prefix
    optimized_payload = dict(body)
    optimized_payload["messages"] = optimized_messages
    if dynamic_injection:
        optimized_payload = cache_guard.stabilize_payload(optimized_payload, dynamic_injection)

    api_key = request.headers.get("x-api-key", os.getenv("ANTHROPIC_API_KEY", ""))

    # 4. Routing logic (OmniRoute)
    # If no API key or fallback requested, route to local Ollama!
    if not api_key:
        logger.info("No Anthropic API key supplied. Routing to local Ollama (%s)...", config.ollama_model)
        ollama_res = await omniroute.route_to_ollama(
            optimized_messages, 
            system_prompt=dynamic_injection,
            stream=False
        )
        assistant_text = ollama_res.get("message", {}).get("content", "")
        # Apply Caveman output compression
        compressed_text, _ = caveman.compress_text(assistant_text)
        
        anthropic_formatted = {
            "id": "msg_ultron_" + os.urandom(8).hex(),
            "type": "message",
            "role": "assistant",
            "model": config.ollama_model,
            "content": [{"type": "text", "text": compressed_text}],
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": comp_tokens_est,
                "output_tokens": len(compressed_text) // 4
            }
        }
        return JSONResponse(anthropic_formatted)

    # Forward to upstream Anthropic
    resp = await omniroute.route_to_anthropic(optimized_payload, api_key)
    
    # If 429 quota exhausted, fallback to local Ollama!
    if resp.status_code == 429:
        logger.warning("Anthropic 429. Falling back to local Ollama (%s)", config.ollama_model)
        ollama_res = await omniroute.route_to_ollama(optimized_messages, dynamic_injection)
        assistant_text = ollama_res.get("message", {}).get("content", "")
        compressed_text, _ = caveman.compress_text(assistant_text)
        return JSONResponse({
            "id": "msg_ultron_fallback_" + os.urandom(8).hex(),
            "type": "message",
            "role": "assistant",
            "model": f"{config.ollama_model}-fallback",
            "content": [{"type": "text", "text": compressed_text}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": comp_tokens_est, "output_tokens": len(compressed_text) // 4}
        })

    # Pass through headers and response
    excluded_headers = {"content-encoding", "content-length", "transfer-encoding", "connection"}
    response_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded_headers}

    return Response(content=resp.content, status_code=resp.status_code, headers=response_headers)

@app.get("/api/breadcrumb/{hash_key}")
async def get_breadcrumb(hash_key: str):
    """Retrieves full uncompressed raw payload by hash."""
    content = breadcrumb_store.retrieve(hash_key)
    if content is None:
        raise HTTPException(status_code=404, detail="Breadcrumb hash not found")
    return {"hash_key": hash_key, "content": content}

@app.get("/metrics")
@app.get("/health")
async def get_metrics():
    """Live telemetry and token savings statistics."""
    telemetry = omniroute.get_telemetry()
    return {
        "status": "healthy",
        "service": "Ultron Token Optimization Engine",
        "version": "1.0.0",
        "telemetry": telemetry,
        "features": {
            "caveman_mode": config.caveman_mode,
            "headroom": config.headroom_enabled,
            "claudemem": config.claudemem_enabled,
            "omniroute": config.omniroute_enabled,
            "prompt_caching_guard": config.cache_guard_enabled
        }
    }
