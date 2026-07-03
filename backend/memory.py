"""
会话持久化模块。
以 JSON 文件形式存储对话历史，不依赖数据库。

存储结构：
  backend/data/sessions/{session_id}.json
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "sessions")


# ---------- 内部工具 ----------

def _ensure_dir():
    """确保数据目录存在。"""
    os.makedirs(DATA_DIR, exist_ok=True)


def _session_path(session_id: str) -> str:
    return os.path.join(DATA_DIR, f"{session_id}.json")


# ---------- 会话 CRUD ----------

def new_session_id() -> str:
    """生成全局唯一的 session_id。"""
    now = datetime.now()
    return f"session__{now.strftime('%Y%m%d')}__{now.strftime('%H%M%S')}"


def save_session(
    session_id: str,
    messages: list,
    summary: str = "",
    user_profile: Optional[dict] = None,
) -> None:
    """
    将会话保存到 JSON 文件。

    Args:
        session_id: 会话 ID
        messages: 消息列表 [{"role": "user"/"assistant", "content": "..."}, ...]
        summary: 可选的对话摘要
    """
    _ensure_dir()
    path = _session_path(session_id)

    # 如果文件已存在，合并更新
    existing = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = {}

    data = {
        **existing,
        "session_id": session_id,
        "messages": messages,
        "message_count": len(messages),
        "last_updated": datetime.now().isoformat(),
    }
    if summary:
        data["conversation_summary"] = summary
    if user_profile:
        data["user_profile"] = user_profile

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_session(session_id: str) -> Optional[dict]:
    """
    从 JSON 文件加载完整会话数据。

    Returns:
        包含 messages、conversation_summary 等的 dict，不存在返回 None
    """
    path = _session_path(session_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def load_session_messages(session_id: str) -> list:
    """仅加载消息列表，不存在返回空列表。"""
    data = load_session(session_id)
    if data is None:
        return []
    return data.get("messages", [])


def load_session_summary(session_id: str) -> str:
    """仅加载摘要文本。"""
    data = load_session(session_id)
    if data is None:
        return ""
    return data.get("conversation_summary", "")


def load_session_profile(session_id: str) -> dict:
    """Load the structured learning profile for a session."""
    data = load_session(session_id)
    if data is None:
        return {}
    return data.get("user_profile", {})


def list_sessions() -> list[dict]:
    """
    列出所有会话的元信息（按最后更新倒序）。

    Returns:
        [{"session_id": "...", "message_count": N, "last_updated": "..."}, ...]
    """
    _ensure_dir()
    sessions = []
    for fname in os.listdir(DATA_DIR):
        if not fname.endswith(".json"):
            continue
        session_id = fname[:-5]  # 去掉 .json
        data = load_session(session_id)
        if data is None:
            continue
        sessions.append({
            "session_id": session_id,
            "message_count": data.get("message_count", 0),
            "last_updated": data.get("last_updated", ""),
            "preview": _preview(data.get("messages", [])),
            "profile": data.get("user_profile", {}),
        })

    # 按最后更新时间倒序
    sessions.sort(key=lambda s: s.get("last_updated", ""), reverse=True)
    return sessions


def delete_session(session_id: str) -> None:
    """删除会话文件。"""
    path = _session_path(session_id)
    if os.path.exists(path):
        os.remove(path)


def _preview(messages: list) -> str:
    """取第一条用户消息作为预览。"""
    for m in messages:
        if isinstance(m, dict) and m.get("role") == "user":
            content = m.get("content", "")
            return content[:50] + "..." if len(content) > 50 else content
        if hasattr(m, "content") and hasattr(m, "type") and m.type == "human":
            content = m.content or ""
            return content[:50] + "..." if len(content) > 50 else content
    return ""
