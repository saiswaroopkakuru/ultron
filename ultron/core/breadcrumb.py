import hashlib
import time
import sqlite3
import re
from contextlib import contextmanager
from typing import Optional, Tuple, Dict, Any
from ultron.config import config

class BreadcrumbStore:
    """
    Content-addressed reversible breadcrumb store and telemetry engine.
    Stores raw uncompressed data and provides deterministic compact breadcrumb tags
    e.g., [ultron:ref:a1b2c3d4:48lines:2140b] that the agent or user can expand on demand.
    """
    def __init__(self, db_path=None):
        self.db_path = str(db_path or config.db_path)
        self._init_db()

    @contextmanager
    def _connect(self):
        # sqlite3's own context manager commits but never closes, which pins the
        # file open. On Windows that blocks deleting a benchmark's temp dir.
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS breadcrumbs (
                    hash_key TEXT PRIMARY KEY,
                    raw_content TEXT NOT NULL,
                    char_len INTEGER NOT NULL,
                    line_count INTEGER NOT NULL,
                    content_type TEXT,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bc_created ON breadcrumbs(created_at)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetry (
                    id TEXT PRIMARY KEY,
                    total_tokens_in INTEGER DEFAULT 0,
                    tokens_saved INTEGER DEFAULT 0,
                    total_raw_bytes INTEGER DEFAULT 0,
                    total_pruned_bytes INTEGER DEFAULT 0,
                    tool_calls_intercepted INTEGER DEFAULT 0,
                    expansions_count INTEGER DEFAULT 0,
                    updated_at REAL NOT NULL
                )
            """)
            # Migrate missing columns if table existed previously
            cur = conn.execute("PRAGMA table_info(telemetry)")
            existing = {r[1] for r in cur.fetchall()}
            for col, col_type in [
                ("total_raw_bytes", "INTEGER DEFAULT 0"),
                ("total_pruned_bytes", "INTEGER DEFAULT 0"),
                ("tool_calls_intercepted", "INTEGER DEFAULT 0"),
                ("expansions_count", "INTEGER DEFAULT 0"),
            ]:
                if col not in existing:
                    try:
                        conn.execute(f"ALTER TABLE telemetry ADD COLUMN {col} {col_type}")
                    except Exception:
                        pass

    def store(self, content: str, content_type: str = "text") -> Tuple[str, str]:
        """
        Stores content and returns (hash_key, breadcrumb_tag).
        Handles prefix collisions by widening the hash prefix without data loss.
        """
        content_bytes = content.encode("utf-8")
        hash_full = hashlib.sha256(content_bytes).hexdigest()
        line_count = content.count("\n") + 1
        byte_len = len(content_bytes)

        with self._connect() as conn:
            hash_short = hash_full[:8]
            for prefix_len in (8, 12, 16, 24, 32, 64):
                hash_short = hash_full[:prefix_len]
                cur = conn.execute(
                    "SELECT raw_content FROM breadcrumbs WHERE hash_key = ?", (hash_short,)
                )
                row = cur.fetchone()
                if row is None or row[0] == content:
                    break

            conn.execute(
                """
                INSERT OR REPLACE INTO breadcrumbs 
                (hash_key, raw_content, char_len, line_count, content_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (hash_short, content, len(content), line_count, content_type, time.time())
            )

        tag = f"[ultron:ref:{hash_short}:{line_count}L:{byte_len}B]"
        return hash_short, tag

    def record_savings(self, raw_bytes: int, comp_bytes: int):
        """Records context pruning savings into telemetry."""
        tok_in = max(1, raw_bytes // 4)
        tok_saved = max(0, (raw_bytes - comp_bytes) // 4)
        pruned_b = max(0, raw_bytes - comp_bytes)

        with self._connect() as conn:
            conn.execute("""
                INSERT INTO telemetry (id, total_tokens_in, tokens_saved, total_raw_bytes, total_pruned_bytes, tool_calls_intercepted, expansions_count, updated_at)
                VALUES ('live', ?, ?, ?, ?, 1, 0, ?)
                ON CONFLICT(id) DO UPDATE SET
                    total_tokens_in = total_tokens_in + excluded.total_tokens_in,
                    tokens_saved = tokens_saved + excluded.tokens_saved,
                    total_raw_bytes = total_raw_bytes + excluded.total_raw_bytes,
                    total_pruned_bytes = total_pruned_bytes + excluded.total_pruned_bytes,
                    tool_calls_intercepted = tool_calls_intercepted + 1,
                    updated_at = excluded.updated_at
            """, (tok_in, tok_saved, raw_bytes, pruned_b, time.time()))

    def record_expansion(self, tokens: int):
        """Records an expansion event."""
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO telemetry (id, total_tokens_in, tokens_saved, total_raw_bytes, total_pruned_bytes, tool_calls_intercepted, expansions_count, updated_at)
                VALUES ('live', 0, 0, 0, 0, 0, 1, ?)
                ON CONFLICT(id) DO UPDATE SET
                    expansions_count = expansions_count + 1,
                    updated_at = excluded.updated_at
            """, (time.time(),))

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns aggregated telemetry metrics."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM telemetry WHERE id = 'live'")
            row = cur.fetchone()
            if row:
                t_in = row["total_tokens_in"]
                t_saved = row["tokens_saved"]
                pct = round((t_saved / t_in * 100), 1) if t_in > 0 else 0.0
                return {
                    "total_tokens_in": t_in,
                    "tokens_saved": t_saved,
                    "savings_percentage": pct,
                    "total_raw_bytes": row["total_raw_bytes"],
                    "total_pruned_bytes": row["total_pruned_bytes"],
                    "tool_calls_intercepted": row["tool_calls_intercepted"],
                    "expansions_count": row["expansions_count"]
                }
            return {
                "total_tokens_in": 0,
                "tokens_saved": 0,
                "savings_percentage": 0.0,
                "total_raw_bytes": 0,
                "total_pruned_bytes": 0,
                "tool_calls_intercepted": 0,
                "expansions_count": 0
            }

    def retrieve(self, hash_key: str) -> Optional[str]:
        """
        Retrieves raw uncompressed content by short hash.
        """
        clean_key = hash_key.replace("ultron:ref:", "").split(":")[0]
        with self._connect() as conn:
            cur = conn.execute("SELECT raw_content FROM breadcrumbs WHERE hash_key = ?", (clean_key,))
            row = cur.fetchone()

        if not row:
            return None

        self.record_expansion(max(1, len(row[0]) // 4))
        return row[0]

    def expand_breadcrumbs_in_text(self, text: str) -> str:
        """
        Expands any breadcrumb references embedded inside a text string.
        """
        pattern = r"\[ultron:ref:([a-f0-9]+):[^\]]+\]"
        
        def _replace(match):
            key = match.group(1)
            raw = self.retrieve(key)
            return raw if raw is not None else match.group(0)

        return re.sub(pattern, _replace, text)

    def prune_old_breadcrumbs(self, days: int = 7) -> int:
        """Deletes breadcrumbs older than the specified days."""
        cutoff = time.time() - (days * 86400)
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM breadcrumbs WHERE created_at < ?", (cutoff,))
            return cur.rowcount

breadcrumb_store = BreadcrumbStore()
