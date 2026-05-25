"""Tests for trace-event-filter."""
import json
import tempfile
import pytest
from trace_event_filter import EventFilter, filter_events, filter_file

EVENTS = [
    {"kind": "llm_call", "model": "claude-sonnet-4-5", "cost_usd": 0.01, "duration_ms": 200, "timestamp": 1000},
    {"kind": "tool_call", "model": "claude-sonnet-4-5", "cost_usd": 0.001, "duration_ms": 50, "timestamp": 1010},
    {"kind": "llm_call", "model": "gpt-5.4", "cost_usd": 0.02, "duration_ms": 400, "timestamp": 1020, "error": "timeout"},
    {"kind": "llm_call", "model": "claude-sonnet-4-5", "cost_usd": 0.005, "duration_ms": 150, "timestamp": 1030},
    {"kind": "tool_call", "cost_usd": 0.0, "duration_ms": 10, "timestamp": 1040},
]

def test_no_filter_returns_all():
    assert len(filter_events(EVENTS)) == 5

def test_filter_by_kind():
    result = filter_events(EVENTS, kind="llm_call")
    assert len(result) == 3
    assert all(e["kind"] == "llm_call" for e in result)

def test_filter_by_kind_list():
    result = filter_events(EVENTS, kind=["llm_call", "tool_call"])
    assert len(result) == 5

def test_filter_by_model():
    result = filter_events(EVENTS, model="claude-sonnet-4-5")
    assert len(result) == 3

def test_filter_by_model_list():
    result = filter_events(EVENTS, model=["claude-sonnet-4-5", "gpt-5.4"])
    assert len(result) == 4

def test_filter_has_error_true():
    result = filter_events(EVENTS, has_error=True)
    assert len(result) == 1
    assert result[0].get("error") == "timeout"

def test_filter_has_error_false():
    result = filter_events(EVENTS, has_error=False)
    assert len(result) == 4

def test_filter_min_cost():
    result = filter_events(EVENTS, min_cost_usd=0.005)
    assert all(e.get("cost_usd", 0) >= 0.005 for e in result)

def test_filter_max_cost():
    result = filter_events(EVENTS, max_cost_usd=0.005)
    assert all(e.get("cost_usd", 0) <= 0.005 for e in result)

def test_filter_cost_range():
    result = filter_events(EVENTS, min_cost_usd=0.005, max_cost_usd=0.01)
    assert len(result) == 2

def test_filter_min_duration():
    result = filter_events(EVENTS, min_duration_ms=200)
    assert all(e.get("duration_ms", 0) >= 200 for e in result)

def test_filter_max_duration():
    result = filter_events(EVENTS, max_duration_ms=100)
    assert all(e.get("duration_ms", 0) <= 100 for e in result)

def test_filter_after_ts():
    result = filter_events(EVENTS, after_ts=1020)
    assert all(e.get("timestamp", 0) >= 1020 for e in result)

def test_filter_before_ts():
    result = filter_events(EVENTS, before_ts=1010)
    assert all(e.get("timestamp", 0) <= 1010 for e in result)

def test_filter_ts_range():
    result = filter_events(EVENTS, after_ts=1010, before_ts=1020)
    assert len(result) == 2

def test_filter_custom_where():
    result = filter_events(EVENTS, where=lambda e: e.get("model") == "gpt-5.4")
    assert len(result) == 1

def test_filter_combined():
    result = filter_events(EVENTS, kind="llm_call", has_error=False, min_cost_usd=0.005)
    assert len(result) == 2

def test_filter_empty_events():
    assert filter_events([]) == []

def test_filter_no_matches():
    result = filter_events(EVENTS, kind="nonexistent")
    assert result == []

def test_filter_does_not_mutate():
    original = list(EVENTS)
    filter_events(EVENTS, kind="llm_call")
    assert EVENTS == original

def test_accepts_variant_kind():
    events = [{"event_type": "llm_call"}]
    result = filter_events(events, kind="llm_call")
    assert len(result) == 1

def test_accepts_variant_model():
    events = [{"model_id": "claude-haiku"}]
    result = filter_events(events, model="claude-haiku")
    assert len(result) == 1

def test_accepts_variant_error():
    events = [{"err": "connection refused"}]
    result = filter_events(events, has_error=True)
    assert len(result) == 1

def test_accepts_variant_timestamp():
    events = [{"ts": 5000}]
    result = filter_events(events, after_ts=4000)
    assert len(result) == 1

def test_accepts_variant_cost():
    events = [{"cost": 0.05}]
    result = filter_events(events, min_cost_usd=0.01)
    assert len(result) == 1

def test_accepts_variant_duration():
    events = [{"latency_ms": 300}]
    result = filter_events(events, min_duration_ms=200)
    assert len(result) == 1

# EventFilter chainable

def test_event_filter_chain_kind():
    result = EventFilter(EVENTS).where_kind("llm_call").result()
    assert len(result) == 3

def test_event_filter_chain_model():
    result = EventFilter(EVENTS).where_model("claude-sonnet-4-5").result()
    assert len(result) == 3

def test_event_filter_chain_no_error():
    result = EventFilter(EVENTS).where_no_error().result()
    assert len(result) == 4

def test_event_filter_chain_has_error():
    result = EventFilter(EVENTS).where_has_error().result()
    assert len(result) == 1

def test_event_filter_chain_cost():
    result = EventFilter(EVENTS).where_cost(min=0.005).result()
    assert len(result) >= 1

def test_event_filter_chain_duration():
    result = EventFilter(EVENTS).where_duration(max=100).result()
    assert len(result) >= 1

def test_event_filter_chain_combined():
    result = (
        EventFilter(EVENTS)
        .where_kind("llm_call")
        .where_no_error()
        .result()
    )
    assert len(result) == 2

def test_event_filter_count():
    f = EventFilter(EVENTS).where_kind("llm_call")
    assert f.count() == 3
    assert len(f) == 3

def test_event_filter_iterable():
    events = list(EventFilter(EVENTS).where_kind("llm_call"))
    assert len(events) == 3

def test_event_filter_where_custom():
    result = EventFilter(EVENTS).where(lambda e: e.get("cost_usd", 0) > 0.015).result()
    assert len(result) == 1

def test_event_filter_multiple_kinds():
    result = EventFilter(EVENTS).where_kind("llm_call", "tool_call").result()
    assert len(result) == 5

def test_event_filter_timestamp():
    result = EventFilter(EVENTS).where_timestamp(after=1020, before=1030).result()
    assert len(result) == 2

# filter_file

def test_filter_file_basic():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for e in EVENTS:
            f.write(json.dumps(e) + "\n")
        path = f.name
    result = filter_file(path, kind="llm_call")
    assert len(result) == 3

def test_filter_file_with_dest():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps(EVENTS[0]) + "\n")
        src = f.name
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        dst = f.name
    filter_file(src, dst)
    written = [json.loads(l) for l in open(dst).read().splitlines() if l.strip()]
    assert len(written) == 1

def test_filter_file_skips_blank_lines():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps(EVENTS[0]) + "\n\n")
        f.write(json.dumps(EVENTS[1]) + "\n")
        path = f.name
    result = filter_file(path)
    assert len(result) == 2
