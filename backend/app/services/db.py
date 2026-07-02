"""SQLite 会话持久化模块。

使用 Python 标准库 sqlite3，零额外依赖。
WAL 模式，支持并发读写。
"""

import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 数据库文件路径
DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DB_DIR / "acss.db"


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接，自动启用 WAL 模式和外键。"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """初始化数据库表（幂等操作）。"""
    conn = _get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id         TEXT PRIMARY KEY,
                title      TEXT DEFAULT '新对话',
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS messages (
                id                TEXT PRIMARY KEY,
                session_id        TEXT NOT NULL,
                role              TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                text              TEXT NOT NULL DEFAULT '',
                intent_label      TEXT,
                intent_confidence REAL,
                sentiment_label   TEXT,
                sentiment_score   REAL,
                created_at        TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, created_at);
        """)
        conn.commit()
        logger.info("SQLite 数据库初始化完成: %s", DB_PATH)
    finally:
        conn.close()


def ensure_session(session_id: str, title: Optional[str] = None) -> None:
    """确保会话存在（幂等），可选设置标题。

    Args:
        session_id: 会话 ID。
        title: 会话标题（仅首次创建时写入）。
    """
    conn = _get_conn()
    try:
        existing = conn.execute(
            "SELECT id FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE sessions SET updated_at = datetime('now', 'localtime') WHERE id = ?",
                (session_id,),
            )
        else:
            conn.execute(
                "INSERT INTO sessions (id, title) VALUES (?, ?)",
                (session_id, title or "新对话"),
            )
        conn.commit()
    finally:
        conn.close()


def save_message(
    msg_id: str,
    session_id: str,
    role: str,
    text: str,
    intent_label: Optional[str] = None,
    intent_confidence: Optional[float] = None,
    sentiment_label: Optional[str] = None,
    sentiment_score: Optional[float] = None,
) -> None:
    """保存一条消息到数据库。

    Args:
        msg_id: 消息唯一 ID。
        session_id: 所属会话 ID。
        role: 'user' 或 'assistant'。
        text: 消息文本。
        intent_label: 意图标签（仅 assistant）。
        intent_confidence: 意图置信度。
        sentiment_label: 情感标签（仅 assistant）。
        sentiment_score: 情感置信度。
    """
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO messages
               (id, session_id, role, text,
                intent_label, intent_confidence,
                sentiment_label, sentiment_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                msg_id, session_id, role, text,
                intent_label, intent_confidence,
                sentiment_label, sentiment_score,
            ),
        )
        conn.execute(
            "UPDATE sessions SET updated_at = datetime('now', 'localtime') WHERE id = ?",
            (session_id,),
        )
        conn.commit()
    finally:
        conn.close()


def get_sessions() -> list[dict]:
    """获取所有会话列表（按更新时间倒序）。

    Returns:
        list[dict]: 每项含 id, title, message_count, updated_at。
    """
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT s.id, s.title, s.updated_at,
                      COUNT(m.id) AS message_count
               FROM sessions s
               LEFT JOIN messages m ON m.session_id = s.id
               GROUP BY s.id
               ORDER BY s.updated_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_session_messages(session_id: str) -> list[dict]:
    """获取某个会话的所有消息（按时间正序）。

    Args:
        session_id: 会话 ID。

    Returns:
        list[dict]: 消息列表。
    """
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT id, session_id, role, text,
                      intent_label, intent_confidence,
                      sentiment_label, sentiment_score,
                      created_at
               FROM messages
               WHERE session_id = ?
               ORDER BY created_at ASC""",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_session(session_id: str) -> Optional[dict]:
    """获取单个会话元信息。

    Args:
        session_id: 会话 ID。

    Returns:
        dict | None: 会话信息或 None。
    """
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_session(session_id: str) -> bool:
    """删除会话及其所有消息。

    Args:
        session_id: 会话 ID。

    Returns:
        bool: 是否成功删除（会话不存在时返回 False）。
    """
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        deleted = cur.rowcount > 0
        if deleted:
            logger.info("会话已删除: %s", session_id)
        return deleted
    finally:
        conn.close()
