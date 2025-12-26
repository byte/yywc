from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .export_reader import Dataset


_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'_-]{1,}")
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_URL_RE = re.compile(r"\bhttps?://\S+\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-. ]?)?(?:\(?\d{2,3}\)?[-. ]?)?\d{3}[-. ]?\d{4}\b")


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "can",
    "do",
    "for",
    "from",
    "have",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "just",
    "like",
    "me",
    "my",
    "not",
    "of",
    "on",
    "or",
    "please",
    "so",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "to",
    "we",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
    "you",
    "your",
}


@dataclass(frozen=True)
class Excerpt:
    conversation_id: str
    title: str
    created_at_iso: str
    role: str
    text: str


@dataclass(frozen=True)
class Summary:
    year: int | None
    total_conversations: int
    total_messages: int
    total_user_messages: int
    total_assistant_messages: int
    total_words: int
    words_per_message: float
    first_message_iso: str | None
    last_message_iso: str | None
    active_days: int
    longest_streak_days: int
    busiest_day_local: str | None
    busiest_day_messages: int
    busiest_hour_local: int | None
    busiest_hour_messages: int
    messages_by_month: dict[str, int]
    messages_by_day_local: dict[str, int]
    messages_by_weekday: dict[str, int]
    messages_by_hour_local: dict[str, int]
    top_words: list[tuple[str, int]]
    top_bigrams: list[tuple[str, int]]
    top_titles: list[tuple[str, int]]
    top_models: list[tuple[str, int]]
    longest_conversations: list[tuple[str, int]]
    excerpts: list[Excerpt]
    fun_facts: list[str]


def _tokenize(text: str) -> list[str]:
    words = [m.group(0).lower() for m in _WORD_RE.finditer(text)]
    words = [w for w in words if w not in _STOPWORDS and not w.isdigit()]
    return words


def _bigrams(tokens: list[str]) -> Iterable[str]:
    for i in range(len(tokens) - 1):
        yield f"{tokens[i]} {tokens[i+1]}"


def _month_key(dt) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def _weekday_key(dt) -> str:
    return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dt.weekday()]


def _redact(text: str) -> str:
    text = _EMAIL_RE.sub("[redacted-email]", text)
    text = _URL_RE.sub("[redacted-url]", text)
    text = _PHONE_RE.sub("[redacted-phone]", text)
    return text


def _compute_longest_streak(days: list[date]) -> int:
    if not days:
        return 0
    days_sorted = sorted(set(days))
    best = 1
    current = 1
    for prev, nxt in zip(days_sorted, days_sorted[1:]):
        if (nxt - prev).days == 1:
            current += 1
            best = max(best, current)
        else:
            current = 1
    return best


def summarize(dataset: Dataset, *, year: int | None, redact: bool, max_excerpts: int) -> Summary:
    messages = dataset.messages

    total_messages = len(messages)
    total_user = sum(1 for m in messages if m.role == "user")
    total_assistant = sum(1 for m in messages if m.role == "assistant")

    conv_ids = {m.conversation_id for m in messages}
    total_conversations = len(conv_ids) if conv_ids else len(dataset.conversations)

    messages_by_month: Counter[str] = Counter()
    messages_by_weekday: Counter[str] = Counter()
    messages_by_day_local: Counter[str] = Counter()
    messages_by_hour_local: Counter[str] = Counter()
    top_titles: Counter[str] = Counter()
    top_models: Counter[str] = Counter()
    words: Counter[str] = Counter()
    bigrams: Counter[str] = Counter()
    conv_message_counts: Counter[str] = Counter()
    active_day_set: set[date] = set()

    first_message_iso: str | None = None
    last_message_iso: str | None = None

    for m in messages:
        first_message_iso = first_message_iso or m.created_at.isoformat()
        last_message_iso = m.created_at.isoformat()

        local_dt = m.created_at.astimezone()
        messages_by_month[_month_key(m.created_at)] += 1
        messages_by_weekday[_weekday_key(m.created_at)] += 1
        messages_by_day_local[local_dt.date().isoformat()] += 1
        messages_by_hour_local[str(local_dt.hour)] += 1
        top_titles[m.conversation_title or "Untitled"] += 1
        if m.model:
            top_models[m.model] += 1
        conv_message_counts[m.conversation_title or "Untitled"] += 1
        active_day_set.add(local_dt.date())

        tokens = _tokenize(m.text)
        words.update(tokens)
        bigrams.update(_bigrams(tokens))

    total_words = sum(words.values())
    words_per_message = (total_words / total_messages) if total_messages else 0.0
    longest_streak = _compute_longest_streak(list(active_day_set))

    def _sorted_counter(counter: Counter[str], limit: int) -> list[tuple[str, int]]:
        return [(k, v) for k, v in counter.most_common(limit) if k]

    excerpts: list[Excerpt] = []
    for m in messages[: max_excerpts * 2]:
        snippet = m.text.strip().replace("\r\n", "\n").replace("\r", "\n")
        snippet = "\n".join(line.strip() for line in snippet.split("\n") if line.strip())
        snippet = snippet[:360] + ("…" if len(snippet) > 360 else "")
        if redact:
            snippet = _redact(snippet)
        if snippet:
            excerpts.append(
                Excerpt(
                    conversation_id=m.conversation_id,
                    title=m.conversation_title or "Untitled",
                    created_at_iso=m.created_at.isoformat(),
                    role=m.role,
                    text=snippet,
                )
            )
        if len(excerpts) >= max_excerpts:
            break

    # Ensure chronological month order in output
    messages_by_month_sorted = dict(sorted(messages_by_month.items(), key=lambda kv: kv[0]))
    messages_by_weekday_sorted = {k: messages_by_weekday[k] for k in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}
    messages_by_day_local_sorted = dict(sorted(messages_by_day_local.items(), key=lambda kv: kv[0]))
    messages_by_hour_local_sorted = {str(h): messages_by_hour_local[str(h)] for h in range(24)}

    busiest_day_local: str | None = None
    busiest_day_messages = 0
    if messages_by_day_local:
        busiest_day_local, busiest_day_messages = max(messages_by_day_local.items(), key=lambda kv: kv[1])

    busiest_hour_local: int | None = None
    busiest_hour_messages = 0
    if messages_by_hour_local:
        hour_key, busiest_hour_messages = max(messages_by_hour_local.items(), key=lambda kv: kv[1])
        try:
            busiest_hour_local = int(hour_key)
        except ValueError:
            busiest_hour_local = None

    def _top_key(counter: Counter[str]) -> str | None:
        return counter.most_common(1)[0][0] if counter else None

    fun_facts: list[str] = []
    top_month = _top_key(messages_by_month)
    top_weekday = _top_key(messages_by_weekday)
    if top_month:
        fun_facts.append(f"Most chatty month: {top_month}")
    if top_weekday:
        fun_facts.append(f"Favorite weekday: {top_weekday}")
    if busiest_hour_local is not None:
        fun_facts.append(f"Peak hour (local): {busiest_hour_local:02d}:00")
    if busiest_day_local:
        fun_facts.append(f"Busiest day: {busiest_day_local} ({busiest_day_messages} messages)")
    if longest_streak:
        fun_facts.append(f"Longest streak: {longest_streak} days")

    longest_conversations = _sorted_counter(conv_message_counts, 10)
    return Summary(
        year=year,
        total_conversations=total_conversations,
        total_messages=total_messages,
        total_user_messages=total_user,
        total_assistant_messages=total_assistant,
        total_words=total_words,
        words_per_message=words_per_message,
        first_message_iso=first_message_iso,
        last_message_iso=last_message_iso,
        active_days=len(active_day_set),
        longest_streak_days=longest_streak,
        busiest_day_local=busiest_day_local,
        busiest_day_messages=busiest_day_messages,
        busiest_hour_local=busiest_hour_local,
        busiest_hour_messages=busiest_hour_messages,
        messages_by_month=messages_by_month_sorted,
        messages_by_day_local=messages_by_day_local_sorted,
        messages_by_weekday=messages_by_weekday_sorted,
        messages_by_hour_local=messages_by_hour_local_sorted,
        top_words=_sorted_counter(words, 30),
        top_bigrams=_sorted_counter(bigrams, 30),
        top_titles=_sorted_counter(top_titles, 15),
        top_models=_sorted_counter(top_models, 10),
        longest_conversations=longest_conversations,
        excerpts=excerpts,
        fun_facts=fun_facts,
    )
