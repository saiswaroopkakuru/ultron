import os
from pathlib import Path
from pydantic import BaseModel, Field

class UltronConfig(BaseModel):
    # Proxy configuration
    host: str = Field(default="127.0.0.1", description="Ultron proxy host")
    port: int = Field(default=8787, description="Ultron proxy port (fallback 20128)")
    fallback_port: int = Field(default=20128, description="Fallback port if primary busy")

    # Upstream providers
    anthropic_upstream: str = Field(
        default=os.getenv("ANTHROPIC_UPSTREAM_URL", "https://api.anthropic.com"),
        description="Upstream Anthropic API URL"
    )
    openai_upstream: str = Field(
        default=os.getenv("OPENAI_UPSTREAM_URL", "https://api.openai.com"),
        description="Upstream OpenAI API URL"
    )
    ollama_url: str = Field(
        default=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
        description="Local Ollama URL for zero-cost open-source LLM routing"
    )
    ollama_model: str = Field(
        default=os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b"),
        description="Local open-source model name"
    )

    # Core engine switches
    caveman_mode: str = Field(
        default=os.getenv("CAVEMAN_MODE", "off"), 
        description=(
            "Filler-word removal for prose: 'adaptive', 'ultra', 'lite', or 'off'. "
            "Defaults to 'off'. It removes conversational filler well, but tool output "
            "is technical text where it measured 0.2-0.4% while still rewriting lossily."
        )
    )
    headroom_enabled: bool = Field(default=True, description="Enable tool & context compression")
    claudemem_enabled: bool = Field(default=True, description="Enable cross-session persistent memory")
    omniroute_enabled: bool = Field(default=True, description="Enable quota-aware model routing")
    cache_guard_enabled: bool = Field(default=True, description="Preserve Anthropic prompt caching")

    # Compression thresholds
    min_compress_chars: int = Field(default=300, description="Minimum characters before compression triggers")
    max_retained_log_lines: int = Field(default=35, description="Max lines kept for large terminal logs")
    breadcrumb_ttl_seconds: int = Field(default=86400, description="Breadcrumb cache TTL (24 hours)")

    # Storage paths
    data_dir: Path = Field(
        default_factory=lambda: Path(os.path.expanduser("~/.ultron")),
        description="Ultron data and memory storage directory"
    )

    @property
    def db_path(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / "memory.db"

config = UltronConfig()
