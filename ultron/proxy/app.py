import os
import json
import logging
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, Response, StreamingResponse
from ultron.config import config
from ultron.core.pruner import pruner
from ultron.core.omniroute import omniroute
from ultron.core.breadcrumb import breadcrumb_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ultron.proxy")

app = FastAPI(title="Ultron AI Zero-Cost Local & Token Optimization Gateway", version="2.0.0")

def compress_request_messages(messages: list) -> tuple:
    """
    Applies Ultron pruner to past tool results and large noisy context turns.
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
                    if isinstance(res_content, str) and len(res_content) > config.min_compress_chars:
                        raw_char_count += len(res_content)
                        compressed, meta = pruner.prune_tool_output(res_content)
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
        elif isinstance(content, str) and len(content) > config.min_compress_chars:
            raw_char_count += len(content)
            compressed, meta = pruner.prune_tool_output(content)
            compressed_char_count += len(compressed)
            new_msg = dict(msg)
            new_msg["content"] = compressed
            new_messages.append(new_msg)
        else:
            new_messages.append(msg)

    return new_messages, raw_char_count, compressed_char_count

@app.post("/v1/messages")
async def handle_anthropic_messages(request: Request):
    """
    Claude Code API Proxy Endpoint.
    1. Intercepts incoming messages and applies Ultron context pruner.
    2. Routes to local Ollama (zero Anthropic credits!) or upstream Anthropic.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    raw_messages = body.get("messages", [])
    optimized_messages, raw_chars, comp_chars = compress_request_messages(raw_messages)
    
    # Record token savings telemetry
    raw_tokens = raw_chars // 4
    comp_tokens = comp_chars // 4
    if raw_tokens > comp_tokens:
        breadcrumb_store.record_savings(raw_tokens, comp_tokens)

    optimized_payload = dict(body)
    optimized_payload["messages"] = optimized_messages

    api_key = request.headers.get("x-api-key", os.getenv("ANTHROPIC_API_KEY", ""))
    force_local = os.getenv("ULTRON_FORCE_LOCAL", "true").lower() in ("true", "1", "yes")
    stream = optimized_payload.get("stream", False)

    # If force_local is True or no real Anthropic API key is provided, route to local Ollama!
    if force_local or not api_key or api_key.startswith("dummy"):
        logger.info("Routing request to local Ollama model '%s' ($0 Anthropic usage credits)...", config.ollama_model)
        if stream:
            return StreamingResponse(
                omniroute.route_to_ollama_stream(optimized_payload),
                media_type="text/event-stream"
            )
        else:
            res = await omniroute.route_to_ollama(optimized_payload)
            return JSONResponse(res)

    # Otherwise forward to Anthropic upstream with automatic fallback
    try:
        resp = await omniroute.route_to_anthropic(optimized_payload, api_key)
        if resp.status_code == 429:
            logger.warning("Anthropic 429 Quota Exhausted! Falling back to local Ollama (%s)", config.ollama_model)
            if stream:
                return StreamingResponse(
                    omniroute.route_to_ollama_stream(optimized_payload),
                    media_type="text/event-stream"
                )
            else:
                res = await omniroute.route_to_ollama(optimized_payload)
                return JSONResponse(res)
        
        excluded_headers = {"content-encoding", "content-length", "transfer-encoding", "connection"}
        response_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded_headers}
        return Response(content=resp.content, status_code=resp.status_code, headers=response_headers)
    except Exception as e:
        logger.error("Error communicating with Anthropic upstream: %s. Falling back to local Ollama.", str(e))
        if stream:
            return StreamingResponse(
                omniroute.route_to_ollama_stream(optimized_payload),
                media_type="text/event-stream"
            )
        else:
            res = await omniroute.route_to_ollama(optimized_payload)
            return JSONResponse(res)

@app.get("/health")
@app.get("/metrics")
async def health_and_metrics():
    telemetry = breadcrumb_store.get_telemetry()
    return {
        "status": "active",
        "service": "Ultron Zero-Cost Local OmniRoute Gateway",
        "ollama_model": config.ollama_model,
        "ollama_url": config.ollama_url,
        "telemetry": telemetry
    }
