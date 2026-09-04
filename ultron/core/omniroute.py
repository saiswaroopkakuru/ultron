import httpx
import json
import time
import sqlite3
import logging
from typing import Dict, Any, Optional, Tuple
from ultron.config import config

logger = logging.getLogger("ultron.omniroute")

class OmniRouteGateway:
    """
    OmniRoute Quota-Aware Gateway & Multi-Model Router.
    Routes requests between Anthropic Claude, OpenAI, and local open-source LLMs (Ollama qwen2.5 / gemma4).
    Persists live routing telemetry and token savings to SQLite.
    """
    def __init__(self):
        self.db_path = str(config.db_path)
        self._init_db()
        self._load_telemetry()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetry (
                    id TEXT PRIMARY KEY,
                    total_tokens_in INTEGER DEFAULT 0,
                    tokens_saved INTEGER DEFAULT 0,
                    savings_percentage REAL DEFAULT 0,
                    requests_anthropic INTEGER DEFAULT 0,
                    requests_ollama INTEGER DEFAULT 0,
                    requests_fallback INTEGER DEFAULT 0,
                    active_model TEXT,
                    updated_at REAL NOT NULL
                )
            """)

    def _load_telemetry(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM telemetry WHERE id = 'live'")
            row = cur.fetchone()
            if row:
                self.total_tokens_in = row["total_tokens_in"]
                self.tokens_saved = row["tokens_saved"]
                self.requests_routed = {
                    "anthropic": row["requests_anthropic"],
                    "ollama": row["requests_ollama"],
                    "fallback": row["requests_fallback"]
                }
            else:
                self.total_tokens_in = 0
                self.tokens_saved = 0
                self.requests_routed = {"anthropic": 0, "ollama": 0, "fallback": 0}

    def _save_telemetry(self):
        pct = (self.tokens_saved / self.total_tokens_in * 100) if self.total_tokens_in > 0 else 0.0
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO telemetry
                (id, total_tokens_in, tokens_saved, savings_percentage, requests_anthropic, requests_ollama, requests_fallback, active_model, updated_at)
                VALUES ('live', ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.total_tokens_in,
                self.tokens_saved,
                round(pct, 2),
                self.requests_routed["anthropic"],
                self.requests_routed["ollama"],
                self.requests_routed["fallback"],
                config.ollama_model,
                time.time()
            ))

    async def route_to_ollama(self, messages: list, system_prompt: str = "", stream: bool = False) -> Dict[str, Any]:
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        for m in messages:
            content = m.get("content", "")
            if isinstance(content, list):
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
        self._save_telemetry()
        return data

    async def route_to_anthropic(self, payload: Dict[str, Any], api_key: str) -> httpx.Response:
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
            self._save_telemetry()
            return resp

    def record_savings(self, raw_tokens: int, compressed_tokens: int):
        diff = max(0, raw_tokens - compressed_tokens)
        self.tokens_saved += diff
        self.total_tokens_in += raw_tokens
        self._save_telemetry()

    def get_telemetry(self) -> Dict[str, Any]:
        # Re-read from disk first. Long-lived processes (the MCP server) load counters
        # once at __init__, so without this they report startup values forever while
        # short-lived hook processes keep writing new totals underneath them.
        self._load_telemetry()
        pct = (self.tokens_saved / self.total_tokens_in * 100) if self.total_tokens_in > 0 else 0.0
        return {
            "total_tokens_in": self.total_tokens_in,
            "tokens_saved": self.tokens_saved,
            "savings_percentage": round(pct, 2),
            "requests_routed": self.requests_routed,
            "active_ollama_model": config.ollama_model
        }

omniroute = OmniRouteGateway()
