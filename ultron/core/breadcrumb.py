import hashlib
import time
import sqlite3
from typing import Optional, Tuple
from ultron.config import config

class BreadcrumbStore:
    """
    Content-addressed reversible breadcrumb store.
    Stores raw uncompressed data and provides deterministic compact breadcrumb tags
    e.g., [ultron:ref:a1b2c3d4:48lines:2140b] that the agent or user can expand on demand.
    """
    def __init__(self, db_path=None):
        self.db_path = str(db_path or config.db_path)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
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

    def store(self, content: str, content_type: str = "text") -> Tuple[str, str]:
        """
        Stores content and returns (hash_key, breadcrumb_tag).
        """
        content_bytes = content.encode("utf-8")
        hash_full = hashlib.sha256(content_bytes).hexdigest()
        hash_short = hash_full[:8]
        line_count = content.count("\n") + 1
        byte_len = len(content_bytes)

        with sqlite3.connect(self.db_path) as conn:
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

    def retrieve(self, hash_key: str) -> Optional[str]:
        """
        Retrieves raw uncompressed content by short hash.
        """
        clean_key = hash_key.replace("ultron:ref:", "").split(":")[0]
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT raw_content FROM breadcrumbs WHERE hash_key = ?", (clean_key,))
            row = cur.fetchone()

        if not row:
            return None

        # Every expansion path (CLI, MCP, proxy, inline text) reaches this method,
        # so the charge-back is recorded once, here.
        try:
            from ultron.core.omniroute import omniroute
            omniroute.record_expansion(max(1, len(row[0]) // 4))
        except Exception:
            pass

        return row[0]

    def expand_breadcrumbs_in_text(self, text: str) -> str:
        """
        Expands any breadcrumb references embedded inside a text string.
        """
        import re
        pattern = r"\[ultron:ref:([a-f0-9]+):[^\]]+\]"
        
        def _replace(match):
            key = match.group(1)
            raw = self.retrieve(key)
            return raw if raw is not None else match.group(0)

        return re.sub(pattern, _replace, text)

breadcrumb_store = BreadcrumbStore()
