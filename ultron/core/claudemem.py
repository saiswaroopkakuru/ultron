import os
import time
import sqlite3
from typing import List, Dict, Any, Optional
from ultron.config import config

class ClaudeMemEngine:
    """
    Persistent Cross-Session Episodic & Semantic Memory (ClaudeMem / CPR).
    Maintains project memory, architectural decisions, recent tasks, and bug fixes.

    Injects only the memories matching the active prompt, which keeps the injection
    small -- tens of tokens for a handful of stored facts. This is a memory store,
    not a token optimiser: there is no raw-history dump it replaces, so it should
    not be credited with a reduction against one.
    """
    def __init__(self, db_path=None):
        self.db_path = str(db_path or config.db_path)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT,
                    project_dir TEXT,
                    importance INTEGER DEFAULT 1,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    project_dir TEXT,
                    summary TEXT,
                    active_branch TEXT,
                    token_savings REAL DEFAULT 0,
                    last_active REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_topic ON memories(topic)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_proj ON memories(project_dir)")
            self._dedupe_and_constrain(conn)

    def _dedupe_and_constrain(self, conn):
        """
        Collapse memories that repeat an identical fact, then keep them unique.

        save_memory used a plain INSERT, so re-saving the same decision appended
        another row every time. Recall then returned the same fact repeatedly and
        spent the tokens this engine exists to save.
        """
        already = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'idx_mem_unique'"
        ).fetchone()
        if already:
            return

        # NULL never equals NULL in a UNIQUE index, so normalise before constraining.
        conn.execute("UPDATE memories SET project_dir = '' WHERE project_dir IS NULL")
        conn.execute("UPDATE memories SET tags = '' WHERE tags IS NULL")

        # Keep the most recent row of each identical fact.
        conn.execute("""
            DELETE FROM memories WHERE id NOT IN (
                SELECT MAX(id) FROM memories GROUP BY topic, content, project_dir
            )
        """)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mem_unique
            ON memories(topic, content, project_dir)
        """)

    def save_memory(self, topic: str, content: str, tags: str = "", project_dir: str = "", importance: int = 1):
        """
        Saves a permanent memory item, refreshing it if the same fact is already held.

        Re-saving a fact keeps one row and bumps its recency and importance, rather
        than appending a duplicate.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO memories (topic, content, tags, project_dir, importance, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(topic, content, project_dir) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    tags = excluded.tags,
                    importance = MAX(memories.importance, excluded.importance)
            """, (topic, content, tags or "", project_dir or "", importance, time.time()))

    def recall_memories(self, query: str, project_dir: str = "", limit: int = 4) -> List[Dict[str, Any]]:
        """
        Retrieves top relevant memories using BM25-like token matching.
        Runs fast locally with zero API cost.
        """
        query_tokens = set(re_tokenize(query.lower()))
        if not query_tokens:
            return []

        results = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if project_dir:
                cur = conn.execute(
                    "SELECT * FROM memories WHERE project_dir = ? OR project_dir = '' ORDER BY updated_at DESC LIMIT 50",
                    (project_dir,)
                )
            else:
                cur = conn.execute("SELECT * FROM memories ORDER BY updated_at DESC LIMIT 50")
            rows = cur.fetchall()

        for row in rows:
            text = f"{row['topic']} {row['content']} {row['tags']}".lower()
            doc_tokens = set(re_tokenize(text))
            intersection = query_tokens.intersection(doc_tokens)
            if intersection:
                score = len(intersection) * row['importance']
                results.append((score, dict(row)))

        results.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in results[:limit]]

    def generate_delta_context(self, current_prompt: str, project_dir: str = "") -> str:
        """
        Generates a compact, highly dense memory injection block (~150-300 tokens)
        tailored specifically to the active prompt.
        """
        relevant = self.recall_memories(current_prompt, project_dir=project_dir, limit=3)
        if not relevant:
            return ""

        lines = ["[ULTRON PERSISTENT MEMORY CONTEXT]"]
        for mem in relevant:
            lines.append(f"- **{mem['topic']}**: {mem['content']}")
        lines.append("[END MEMORY CONTEXT]")
        return "\n".join(lines)

    def checkpoint_session(self, session_id: str, summary: str, project_dir: str = "", active_branch: str = "", token_savings: float = 0):
        """CPR (Compress, Preserve & Resume) session checkpoint."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sessions 
                (session_id, project_dir, summary, active_branch, token_savings, last_active)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, project_dir, summary, active_branch, token_savings, time.time()))

    def get_latest_session(self, project_dir: str = "") -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if project_dir:
                cur = conn.execute(
                    "SELECT * FROM sessions WHERE project_dir = ? ORDER BY last_active DESC LIMIT 1",
                    (project_dir,)
                )
            else:
                cur = conn.execute("SELECT * FROM sessions ORDER BY last_active DESC LIMIT 1")
            row = cur.fetchone()
            return dict(row) if row else None

def re_tokenize(text: str) -> List[str]:
    import re
    return [w for w in re.findall(r"\w+", text) if len(w) > 2]

claudemem = ClaudeMemEngine()
