import httpx
import json
import logging
from typing import Dict, Any, Optional, Tuple
from ultron.config import config

logger = logging.getLogger("ultron.omniroute")

class OmniRouteGateway:
    """
    OmniRoute Quota-Aware Gateway & Multi-Model Router.
    Routes requests between Anthropic Claude, OpenAI, and local open-source LLMs (Ollama gemma4:26b).
    Features:
    - Automatic fallback ladder if primary model hits 429 quota or rate limits
    - Offloads local summarization & memory jobs to Ollama (zero cloud tokens)
    - Token accounting & cost savings tracker
    """
    def __init__(self):
        self.total_tokens_in = 0
        self.total_tokens_out = 0
        self.tokens_saved = 0
        self.requests_routed = {"anthropic": 0, "ollama": 0, "fallback": 0}

    async def route_to_ollama(self, messages: list, system_prompt: str = "", stream: bool = False) -> Dict[str, Any]:
        """
        Routes request to local Ollama (e.g. gemma4:26b).
        Consumes 0 cloud tokens and operates completely offline.
        """
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        for m in messages:
            content = m.get("content", "")
            if isinstance(content, list):
                # Flatten Anthropic content blocks
                text_parts = [b.get("text", "") for b in content if b.get("type") == "text"]
                content = " ".join(text_parts)
            formatted_messages.append({"role": m.get("role", "user"), "content": content})

        url = f"{config.ollama_url}/api/chat"
        payload = {
            "model": config.ollama_model,
            "messages": formatted_messages,
            "stream": stream,
            "options": {"temperature": 0.2}
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        self.requests_routed["ollama"] += 1
        return data

    async def route_to_anthropic(self, payload: Dict[str, Any], api_key: str) -> httpx.Response:
        """
        Routes request to upstream Anthropic API with quota-aware error handling.
        """
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        url = f"{config.anthropic_upstream}/v1/messages"
        
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 429:
                logger.warning("Anthropic 429 Rate Limit hit. Initiating OmniRoute fallback ladder...")
                self.requests_routed["fallback"] += 1
            else:
                self.requests_routed["anthropic"] += 1
            return resp

    def record_savings(self, raw_tokens: int, compressed_tokens: int):
        diff = max(0, raw_tokens - compressed_tokens)
        self.tokens_saved += diff
        self.total_tokens_in += raw_tokens

    def get_telemetry(self) -> Dict[str, Any]:
        pct = (self.tokens_saved / self.total_tokens_in * 100) if self.total_tokens_in > 0 else 0.0
        return {
            "total_tokens_in": self.total_tokens_in,
            "tokens_saved": self.tokens_saved,
            "savings_percentage": round(pct, 2),
            "requests_routed": self.requests_routed,
            "active_ollama_model": config.ollama_model
        }

omniroute = OmniRouteGateway()
