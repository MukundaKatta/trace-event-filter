"""Filter agent JSONL trace events by field values.

Supports kind, model, error presence, cost/duration ranges, timestamp ranges.
Accepts canonical field names from trace-field-normalize and common variants.

Zero dependencies — standard library only.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path


# ---------------------------------------------------------------------------
# Field helpers — accept canonical + common variants
# ---------------------------------------------------------------------------

def _get_kind(event: dict) -> str | None:
    for k in ("kind", "event_type", "type", "event_kind"):
        v = event.get(k)
        if v and isinstance(v, str):
            return v
    return None


def _get_model(event: dict) -> str | None:
    for k in ("model", "model_id", "model_name"):
        v = event.get(k)
        if v and isinstance(v, str):
            return v
    return None


def _get_float(event: dict, *keys: str) -> float | None:
    for k in keys:
        v = event.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


def _has_error(event: dict) -> bool:
    for k in ("error", "err", "exception", "error_message"):
        v = event.get(k)
        if v:
            return True
    return False


def _get_timestamp(event: dict) -> float | None:
    return _get_float(event, "timestamp", "ts", "time", "created_at", "event_time")


# ---------------------------------------------------------------------------
# Predicate-based filter
# ---------------------------------------------------------------------------

def _matches(
    event: dict,
    *,
    kind: str | list[str] | None = None,
    model: str | list[str] | None = None,
    has_error: bool | None = None,
    min_cost_usd: float | None = None,
    max_cost_usd: float | None = None,
    min_duration_ms: float | None = None,
    max_duration_ms: float | None = None,
    after_ts: float | None = None,
    before_ts: float | None = None,
    where: Callable[[dict], bool] | None = None,
) -> bool:
    if kind is not None:
        kinds = [kind] if isinstance(kind, str) else kind
        if _get_kind(event) not in kinds:
            return False

    if model is not None:
        models = [model] if isinstance(model, str) else model
        if _get_model(event) not in models:
            return False

    if has_error is not None:
        if _has_error(event) != has_error:
            return False

    cost = _get_float(event, "cost_usd", "cost", "price_usd")
    if min_cost_usd is not None and (cost is None or cost < min_cost_usd):
        return False
    if max_cost_usd is not None and (cost is None or cost > max_cost_usd):
        return False

    dur = _get_float(event, "duration_ms", "latency_ms", "elapsed_ms")
    if min_duration_ms is not None and (dur is None or dur < min_duration_ms):
        return False
    if max_duration_ms is not None and (dur is None or dur > max_duration_ms):
        return False

    ts = _get_timestamp(event)
    if after_ts is not None and (ts is None or ts < after_ts):
        return False
    if before_ts is not None and (ts is None or ts > before_ts):
        return False

    if where is not None and not where(event):
        return False

    return True


def filter_events(
    events: list[dict],
    *,
    kind: str | list[str] | None = None,
    model: str | list[str] | None = None,
    has_error: bool | None = None,
    min_cost_usd: float | None = None,
    max_cost_usd: float | None = None,
    min_duration_ms: float | None = None,
    max_duration_ms: float | None = None,
    after_ts: float | None = None,
    before_ts: float | None = None,
    where: Callable[[dict], bool] | None = None,
) -> list[dict]:
    """Filter a list of event dicts by field values.

    Args:
        events: list of event dicts.
        kind: keep events whose kind matches (str or list of str).
        model: keep events whose model matches (str or list of str).
        has_error: if True, keep only error events; if False, only non-error events.
        min_cost_usd / max_cost_usd: cost range filter.
        min_duration_ms / max_duration_ms: duration range filter.
        after_ts / before_ts: timestamp range filter (Unix epoch).
        where: custom callable(event) -> bool for arbitrary filtering.

    Returns:
        New list of matching events (originals not modified).
    """
    return [
        e for e in events
        if _matches(
            e, kind=kind, model=model, has_error=has_error,
            min_cost_usd=min_cost_usd, max_cost_usd=max_cost_usd,
            min_duration_ms=min_duration_ms, max_duration_ms=max_duration_ms,
            after_ts=after_ts, before_ts=before_ts, where=where,
        )
    ]


def filter_file(
    source: str | Path,
    dest: str | Path | None = None,
    **kwargs,
) -> list[dict]:
    """Load a JSONL file, filter events, and optionally write to dest.

    Returns:
        List of matching event dicts.
    """
    p = Path(source)
    events: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass

    filtered = filter_events(events, **kwargs)

    if dest is not None:
        Path(dest).write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in filtered) + "\n",
            encoding="utf-8",
        )

    return filtered


# ---------------------------------------------------------------------------
# Chainable EventFilter class
# ---------------------------------------------------------------------------

class EventFilter:
    """Chainable filter for agent trace event lists.

    Example::

        events = (
            EventFilter(raw_events)
            .where_kind("llm_call")
            .where_model("claude-sonnet-4-5")
            .where_no_error()
            .where_cost(max=0.01)
            .result()
        )
    """

    def __init__(self, events: list[dict]) -> None:
        self._events = list(events)

    def where_kind(self, *kinds: str) -> "EventFilter":
        return EventFilter(filter_events(self._events, kind=list(kinds)))

    def where_model(self, *models: str) -> "EventFilter":
        return EventFilter(filter_events(self._events, model=list(models)))

    def where_has_error(self) -> "EventFilter":
        return EventFilter(filter_events(self._events, has_error=True))

    def where_no_error(self) -> "EventFilter":
        return EventFilter(filter_events(self._events, has_error=False))

    def where_cost(self, *, min: float | None = None, max: float | None = None) -> "EventFilter":
        return EventFilter(filter_events(self._events, min_cost_usd=min, max_cost_usd=max))

    def where_duration(self, *, min: float | None = None, max: float | None = None) -> "EventFilter":
        return EventFilter(filter_events(self._events, min_duration_ms=min, max_duration_ms=max))

    def where_timestamp(self, *, after: float | None = None, before: float | None = None) -> "EventFilter":
        return EventFilter(filter_events(self._events, after_ts=after, before_ts=before))

    def where(self, fn: Callable[[dict], bool]) -> "EventFilter":
        return EventFilter(filter_events(self._events, where=fn))

    def result(self) -> list[dict]:
        return list(self._events)

    def count(self) -> int:
        return len(self._events)

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> "Iterator[dict]":
        return iter(self._events)
