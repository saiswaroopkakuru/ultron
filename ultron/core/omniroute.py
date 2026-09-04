import httpx
import json
import time
import os
import uuid
import logging
from typing import Dict, Any, List, Optional, AsyncIterator
from ultron.config import config
from ultron.core.breadcrumb import breadcrumb_store

logger = logging.getLogger("ultron.omniroute")

class OmniRouteGateway:
    """
    OmniRoute: Zero-Cost Local Routing and Fallback Gateway.
    Translates Anthropic /v1/messages requests to Ollama /api/chat format.
    Allows Claude Code to run locally with zero Anthropic usage credits.
    """
    def __init__(self):
        pass

    def translate_anthropic_to_ollama(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts an Anthropic /v1/messages payload to an Ollama /api/chat payload.
        """
        system_prompt = payload.get("system", "")
        if isinstance(system_prompt, list):
            system_prompt = " ".join([b.get("text", "") for b in system_prompt if isinstance(b, dict)])

        ollama_messages = []
        if system_prompt:
            ollama_messages.append({"role": "system", "content": system_prompt})

        raw_messages = payload.get("messages", [])
        for m in raw_messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            
            if isinstance(content, str):
                ollama_messages.append({"role": role, "content": content})
            elif isinstance(content, list):
                text_parts = []
                tool_calls = []
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    btype = b.get("type")
                    if btype == "text":
                        text_parts.append(b.get("text", ""))
                    elif btype == "tool_use":
                        tool_calls.append({
                            "id": b.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": b.get("name", ""),
                                "arguments": b.get("input", {})
                            }
                        })
                    elif btype == "tool_result":
                        res_content = b.get("content", "")
                        if isinstance(res_content, list):
                            res_content = " ".join([x.get("text", "") for x in res_content if isinstance(x, dict)])
                        text_parts.append(f"[Tool Result ({b.get('tool_use_id', '')})]:\n{res_content}")

                msg_obj: Dict[str, Any] = {"role": role, "content": "\n".join(text_parts)}
                if tool_calls:
                    msg_obj["tool_calls"] = tool_calls
                ollama_messages.append(msg_obj)

        # Translate tools
        ollama_tools = []
        anthropic_tools = payload.get("tools", [])
        for t in anthropic_tools:
            if isinstance(t, dict):
                ollama_tools.append({
                    "type": "function",
                    "function": {
                        "name": t.get("name", ""),
                        "description": t.get("description", ""),
                        "parameters": t.get("input_schema", {})
                    }
                })

        model_name = config.ollama_model
        ollama_payload: Dict[str, Any] = {
            "model": model_name,
            "messages": ollama_messages,
            "stream": payload.get("stream", False),
            "options": {
                "temperature": payload.get("temperature", 0.2)
            }
        }
        if ollama_tools:
            ollama_payload["tools"] = ollama_tools

        return ollama_payload

    async def route_to_ollama(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routes a non-streaming request to local Ollama and converts the response
        into Anthropic /v1/messages format.
        """
        ollama_payload = self.translate_anthropic_to_ollama(payload)
        ollama_payload["stream"] = False
        url = f"{config.ollama_url}/api/chat"

        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(url, json=ollama_payload)
            resp.raise_for_status()
            data = resp.json()

        msg = data.get("message", {})
        content_str = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])

        content_blocks = []
        stop_reason = "end_turn"

        if content_str:
            content_blocks.append({"type": "text", "text": content_str})

        if tool_calls:
            stop_reason = "tool_use"
            for idx, tc in enumerate(tool_calls):
                func = tc.get("function", {})
                args = func.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        pass
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc.get("id") or f"toolu_local_{idx}_{uuid.uuid4().hex[:8]}",
                    "name": func.get("name", ""),
                    "input": args
                })

        if not content_blocks:
            content_blocks.append({"type": "text", "text": ""})

        in_tokens = data.get("prompt_eval_count", 100)
        out_tokens = data.get("eval_count", 50)

        return {
            "id": f"msg_ultron_{uuid.uuid4().hex[:12]}",
            "type": "message",
            "role": "assistant",
            "model": config.ollama_model,
            "content": content_blocks,
            "stop_reason": stop_reason,
            "usage": {
                "input_tokens": in_tokens,
                "output_tokens": out_tokens
            }
        }

    async def route_to_ollama_stream(self, payload: Dict[str, Any]) -> AsyncIterator[str]:
        """
        Streams response from Ollama and yields Anthropic SSE format events.
        """
        ollama_payload = self.translate_anthropic_to_ollama(payload)
        ollama_payload["stream"] = True
        url = f"{config.ollama_url}/api/chat"
        msg_id = f"msg_ultron_{uuid.uuid4().hex[:12]}"

        # 1. message_start
        yield f"event: message_start\ndata: {json.dumps({'type': 'message_start', 'message': {'id': msg_id, 'type': 'message', 'role': 'assistant', 'model': config.ollama_model, 'content': [], 'stop_reason': None, 'usage': {'input_tokens': 0, 'output_tokens': 0}}})}\n\n"

        # 2. content_block_start
        yield f"event: content_block_start\ndata: {json.dumps({'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}})}\n\n"

        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream("POST", url, json=ollama_payload) as response:
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except Exception:
                        continue

                    delta_text = chunk.get("message", {}).get("content", "")
                    if delta_text:
                        yield f"event: content_block_delta\ndata: {json.dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': delta_text}})}\n\n"

                    if chunk.get("done", False):
                        eval_count = chunk.get("eval_count", 0)
                        # content_block_stop
                        yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
                        # message_delta
                        yield f"event: message_delta\ndata: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': eval_count}})}\n\n"
                        # message_stop
                        yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"
                        break

    async def route_to_anthropic(self, payload: Dict[str, Any], api_key: str) -> httpx.Response:
        """
        Forwards request to upstream Anthropic API.
        """
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        url = f"{config.anthropic_upstream}/v1/messages"
        async with httpx.AsyncClient(timeout=180.0) as client:
            return await client.post(url, json=payload, headers=headers)

omniroute = OmniRouteGateway()
