import os
from pathlib import Path
from pydantic import BaseModel, Field

class UltronConfig(BaseModel):
    # Core engine switches
    pruner_enabled: bool = Field(default=True, description="Enable tool & context pruner")
    router_enabled: bool = Field(default=True, description="Enable context-aware plugin router")
    cache_guard_enabled: bool = Field(default=True, description="Preserve Anthropic prompt caching")

    # Compression thresholds
    min_compress_chars: int = Field(default=120, description="Minimum characters before compression triggers")
    max_retained_log_lines: int = Field(default=35, description="Max lines kept for large terminal logs")
    breadcrumb_ttl_seconds: int = Field(default=604800, description="Breadcrumb cache TTL (7 days)")

    # Upstream providers (for benchmark evals)
    ollama_url: str = Field(
        default=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
        description="Local Ollama URL for benchmark evaluations"
    )
    ollama_model: str = Field(
        default=os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b"),
        description="Local model name for benchmark evaluations"
    )

    # Storage paths
    data_dir: Path = Field(
        default_factory=lambda: Path(
            os.path.expanduser(os.getenv("ULTRON_DATA_DIR", "~/.ultron"))
        ),
        description="Ultron data and memory storage directory (override: ULTRON_DATA_DIR)"
    )

    @property
    def db_path(self) -> Path:
        # ULTRON_DB_PATH points at a specific file and wins over data_dir. Benchmarks
        # and tests set it so synthetic payloads never land in live telemetry.
        override = os.getenv("ULTRON_DB_PATH")
        if override:
            path = Path(os.path.expanduser(override))
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / "memory.db"

config = UltronConfig()
