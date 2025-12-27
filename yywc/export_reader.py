from __future__ import annotations

import json
import tempfile
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class Message:
    conversation_id: str
    conversation_title: str
    message_id: str
    role: str
    created_at: datetime
    text: str
    model: str | None


@dataclass(frozen=True)
class Conversation:
    conversation_id: str
    title: str
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class Dataset:
    conversations: list[Conversation]
    messages: list[Message]
    source: str = "chatgpt"  # "chatgpt" or "claude"


def _dt_from_ts(ts: Any) -> datetime | None:
    if ts is None:
        return None
    try:
        value = float(ts)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc)


def _dt_from_iso(iso_str: Any) -> datetime | None:
    if not isinstance(iso_str, str):
        return None
    try:
        # Handle ISO 8601 format: 2024-08-21T08:04:03.586168Z
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _extract_text_from_content(content: Any) -> str:
    if not isinstance(content, dict):
        return ""
    content_type = content.get("content_type")
    if content_type == "text":
        parts = content.get("parts")
        if isinstance(parts, list):
            return "\n".join(str(p) for p in parts if p is not None).strip()
    if content_type == "multimodal_text":
        parts = content.get("parts")
        if isinstance(parts, list):
            chunks: list[str] = []
            for part in parts:
                if isinstance(part, str):
                    chunks.append(part)
                elif isinstance(part, dict) and "text" in part:
                    chunks.append(str(part.get("text") or ""))
            return "\n".join(c for c in chunks if c).strip()
    return ""


def _iter_messages(conversation: dict[str, Any]) -> Iterable[dict[str, Any]]:
    mapping = conversation.get("mapping")
    if not isinstance(mapping, dict):
        return []
    for _, node in mapping.items():
        if isinstance(node, dict) and node.get("message"):
            msg = node["message"]
            if isinstance(msg, dict):
                yield msg


def _get_role(message: dict[str, Any]) -> str:
    author = message.get("author")
    if isinstance(author, dict):
        role = author.get("role")
        if isinstance(role, str):
            return role
    return "unknown"


def _get_model(message: dict[str, Any]) -> str | None:
    metadata = message.get("metadata")
    if not isinstance(metadata, dict):
        return None
    for key in ("model_slug", "model", "model_name"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _load_conversations_json(source_dir: Path) -> list[dict[str, Any]]:
    path = source_dir / "conversations.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("conversations.json is not a list")
    return [c for c in data if isinstance(c, dict)]


def _detect_export_source(conversations: list[dict[str, Any]]) -> str:
    """Detect whether the export is from ChatGPT or Claude."""
    if not conversations:
        return "unknown"
    sample = conversations[0]
    # Claude exports have 'chat_messages' and 'uuid'
    if "chat_messages" in sample and "uuid" in sample:
        return "claude"
    # ChatGPT exports have 'mapping' and 'id'
    if "mapping" in sample and "id" in sample:
        return "chatgpt"
    return "unknown"


def _claude_sender_to_role(sender: str) -> str:
    """Map Claude's sender field to standard role names."""
    mapping = {"human": "user", "assistant": "assistant"}
    return mapping.get(sender, sender)


def _extract_claude_text(message: dict[str, Any]) -> str:
    """Extract text from Claude message format."""
    # Primary: use the 'text' field directly
    text = message.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    # Fallback: extract from content array
    content = message.get("content")
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                t = item.get("text")
                if isinstance(t, str) and t.strip():
                    chunks.append(t.strip())
        return "\n".join(chunks)
    return ""


def _read_claude_export(
    conversations_raw: list[dict[str, Any]],
    *,
    year: int | None,
    role_scope: set[str],
) -> Dataset:
    """Parse Claude export format."""
    conversations: list[Conversation] = []
    messages: list[Message] = []

    for conv in conversations_raw:
        conv_id = str(conv.get("uuid") or "")
        title = str(conv.get("name") or "Untitled")
        created_at = _dt_from_iso(conv.get("created_at"))
        updated_at = _dt_from_iso(conv.get("updated_at"))
        conversations.append(
            Conversation(
                conversation_id=conv_id,
                title=title,
                created_at=created_at,
                updated_at=updated_at,
            )
        )

        chat_messages = conv.get("chat_messages")
        if not isinstance(chat_messages, list):
            continue

        for msg in chat_messages:
            if not isinstance(msg, dict):
                continue
            created = _dt_from_iso(msg.get("created_at"))
            if created is None:
                continue
            if year is not None and created.year != year:
                continue
            sender = msg.get("sender", "")
            role = _claude_sender_to_role(sender)
            if role not in role_scope:
                continue
            text = _extract_claude_text(msg)
            if not text:
                continue
            messages.append(
                Message(
                    conversation_id=conv_id,
                    conversation_title=title,
                    message_id=str(msg.get("uuid") or ""),
                    role=role,
                    created_at=created,
                    text=text,
                    model=None,  # Claude exports don't include model info
                )
            )

    messages.sort(key=lambda m: (m.created_at, m.conversation_id, m.message_id))
    return Dataset(conversations=conversations, messages=messages, source="claude")


@contextmanager
def _open_export_source(export_path: Path, extract_dir: Path | None):
    if export_path.is_dir():
        yield export_path
        return
    if export_path.is_file() and export_path.suffix.lower() == ".zip":
        if extract_dir is not None:
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(export_path, "r") as zf:
                zf.extractall(extract_dir)
            yield extract_dir
            return

        with tempfile.TemporaryDirectory(prefix="yywc_") as tmp:
            tmp_path = Path(tmp)
            with zipfile.ZipFile(export_path, "r") as zf:
                zf.extractall(tmp_path)
            yield tmp_path
            return
    raise FileNotFoundError(f"Export path not found or unsupported: {export_path}")


def _read_chatgpt_export(
    conversations_raw: list[dict[str, Any]],
    *,
    year: int | None,
    role_scope: set[str],
) -> Dataset:
    """Parse ChatGPT export format."""
    conversations: list[Conversation] = []
    messages: list[Message] = []

    for conv in conversations_raw:
        conv_id = str(conv.get("id") or "")
        title = str(conv.get("title") or "Untitled")
        created_at = _dt_from_ts(conv.get("create_time"))
        updated_at = _dt_from_ts(conv.get("update_time"))
        conversations.append(
            Conversation(
                conversation_id=conv_id,
                title=title,
                created_at=created_at,
                updated_at=updated_at,
            )
        )

        for msg in _iter_messages(conv):
            created = _dt_from_ts(msg.get("create_time"))
            if created is None:
                continue
            if year is not None and created.year != year:
                continue
            role = _get_role(msg)
            if role not in role_scope:
                continue
            content = msg.get("content")
            text = _extract_text_from_content(content)
            if not text:
                continue
            messages.append(
                Message(
                    conversation_id=conv_id,
                    conversation_title=title,
                    message_id=str(msg.get("id") or ""),
                    role=role,
                    created_at=created,
                    text=text,
                    model=_get_model(msg),
                )
            )

    messages.sort(key=lambda m: (m.created_at, m.conversation_id, m.message_id))
    return Dataset(conversations=conversations, messages=messages, source="chatgpt")


def read_export(
    export_path: Path,
    *,
    year: int | None,
    role_scope: set[str],
    extract_dir: Path | None = None,
) -> Dataset:
    with _open_export_source(export_path, extract_dir=extract_dir) as source_dir:
        conversations_raw = _load_conversations_json(source_dir)
        source = _detect_export_source(conversations_raw)

        if source == "claude":
            return _read_claude_export(
                conversations_raw, year=year, role_scope=role_scope
            )
        else:
            # Default to ChatGPT parser
            return _read_chatgpt_export(
                conversations_raw, year=year, role_scope=role_scope
            )
