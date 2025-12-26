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


def _dt_from_ts(ts: Any) -> datetime | None:
    if ts is None:
        return None
    try:
        value = float(ts)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc)


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


def read_export(
    export_path: Path,
    *,
    year: int | None,
    role_scope: set[str],
    extract_dir: Path | None = None,
) -> Dataset:
    with _open_export_source(export_path, extract_dir=extract_dir) as source_dir:
        conversations_raw = _load_conversations_json(source_dir)

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
        return Dataset(conversations=conversations, messages=messages)
