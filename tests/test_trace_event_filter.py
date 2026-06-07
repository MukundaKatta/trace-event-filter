"""Tests for trace-event-filter.

Uses only the Python standard library (``unittest``). Run with::

    python3 -m unittest discover -s tests
"""

import json
import os
import sys
import tempfile
import unittest

# Make ``src`` importable when running the tests in-place (without an install).
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
)

from trace_event_filter import EventFilter, filter_events, filter_file  # noqa: E402

EVENTS = [
    {"kind": "llm_call", "model": "claude-sonnet-4-5", "cost_usd": 0.01, "duration_ms": 200, "timestamp": 1000},
    {"kind": "tool_call", "model": "claude-sonnet-4-5", "cost_usd": 0.001, "duration_ms": 50, "timestamp": 1010},
    {"kind": "llm_call", "model": "gpt-5.4", "cost_usd": 0.02, "duration_ms": 400, "timestamp": 1020, "error": "timeout"},
    {"kind": "llm_call", "model": "claude-sonnet-4-5", "cost_usd": 0.005, "duration_ms": 150, "timestamp": 1030},
    {"kind": "tool_call", "cost_usd": 0.0, "duration_ms": 10, "timestamp": 1040},
]


class FilterEventsTests(unittest.TestCase):
    def test_no_filter_returns_all(self):
        self.assertEqual(len(filter_events(EVENTS)), 5)

    def test_filter_by_kind(self):
        result = filter_events(EVENTS, kind="llm_call")
        self.assertEqual(len(result), 3)
        self.assertTrue(all(e["kind"] == "llm_call" for e in result))

    def test_filter_by_kind_list(self):
        result = filter_events(EVENTS, kind=["llm_call", "tool_call"])
        self.assertEqual(len(result), 5)

    def test_filter_by_model(self):
        result = filter_events(EVENTS, model="claude-sonnet-4-5")
        self.assertEqual(len(result), 3)

    def test_filter_by_model_list(self):
        result = filter_events(EVENTS, model=["claude-sonnet-4-5", "gpt-5.4"])
        self.assertEqual(len(result), 4)

    def test_filter_has_error_true(self):
        result = filter_events(EVENTS, has_error=True)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].get("error"), "timeout")

    def test_filter_has_error_false(self):
        result = filter_events(EVENTS, has_error=False)
        self.assertEqual(len(result), 4)

    def test_filter_min_cost(self):
        result = filter_events(EVENTS, min_cost_usd=0.005)
        self.assertTrue(all(e.get("cost_usd", 0) >= 0.005 for e in result))

    def test_filter_max_cost(self):
        result = filter_events(EVENTS, max_cost_usd=0.005)
        self.assertTrue(all(e.get("cost_usd", 0) <= 0.005 for e in result))

    def test_filter_cost_range(self):
        result = filter_events(EVENTS, min_cost_usd=0.005, max_cost_usd=0.01)
        self.assertEqual(len(result), 2)

    def test_filter_min_duration(self):
        result = filter_events(EVENTS, min_duration_ms=200)
        self.assertTrue(all(e.get("duration_ms", 0) >= 200 for e in result))

    def test_filter_max_duration(self):
        result = filter_events(EVENTS, max_duration_ms=100)
        self.assertTrue(all(e.get("duration_ms", 0) <= 100 for e in result))

    def test_filter_after_ts(self):
        result = filter_events(EVENTS, after_ts=1020)
        self.assertTrue(all(e.get("timestamp", 0) >= 1020 for e in result))

    def test_filter_before_ts(self):
        result = filter_events(EVENTS, before_ts=1010)
        self.assertTrue(all(e.get("timestamp", 0) <= 1010 for e in result))

    def test_filter_ts_range(self):
        result = filter_events(EVENTS, after_ts=1010, before_ts=1020)
        self.assertEqual(len(result), 2)

    def test_filter_custom_where(self):
        result = filter_events(EVENTS, where=lambda e: e.get("model") == "gpt-5.4")
        self.assertEqual(len(result), 1)

    def test_filter_combined(self):
        result = filter_events(EVENTS, kind="llm_call", has_error=False, min_cost_usd=0.005)
        self.assertEqual(len(result), 2)

    def test_filter_empty_events(self):
        self.assertEqual(filter_events([]), [])

    def test_filter_no_matches(self):
        result = filter_events(EVENTS, kind="nonexistent")
        self.assertEqual(result, [])

    def test_filter_does_not_mutate(self):
        original = [dict(e) for e in EVENTS]
        filter_events(EVENTS, kind="llm_call")
        self.assertEqual(EVENTS, original)

    def test_returns_new_list(self):
        # The returned list must be independent of the input list object.
        result = filter_events(EVENTS)
        self.assertIsNot(result, EVENTS)

    def test_cost_filter_excludes_events_without_cost(self):
        # Events that lack a cost field cannot satisfy a numeric cost bound.
        events = [{"kind": "note"}]
        self.assertEqual(filter_events(events, min_cost_usd=0.0), [])

    def test_duration_filter_excludes_events_without_duration(self):
        events = [{"kind": "note"}]
        self.assertEqual(filter_events(events, max_duration_ms=1000), [])

    def test_timestamp_filter_excludes_events_without_ts(self):
        events = [{"kind": "note"}]
        self.assertEqual(filter_events(events, after_ts=0), [])


class VariantFieldNameTests(unittest.TestCase):
    def test_accepts_variant_kind(self):
        result = filter_events([{"event_type": "llm_call"}], kind="llm_call")
        self.assertEqual(len(result), 1)

    def test_accepts_variant_kind_type(self):
        result = filter_events([{"type": "tool_call"}], kind="tool_call")
        self.assertEqual(len(result), 1)

    def test_accepts_variant_model(self):
        result = filter_events([{"model_id": "claude-haiku"}], model="claude-haiku")
        self.assertEqual(len(result), 1)

    def test_accepts_variant_error(self):
        result = filter_events([{"err": "connection refused"}], has_error=True)
        self.assertEqual(len(result), 1)

    def test_accepts_variant_exception(self):
        result = filter_events([{"exception": "ValueError"}], has_error=True)
        self.assertEqual(len(result), 1)

    def test_accepts_variant_timestamp(self):
        result = filter_events([{"ts": 5000}], after_ts=4000)
        self.assertEqual(len(result), 1)

    def test_accepts_variant_cost(self):
        result = filter_events([{"cost": 0.05}], min_cost_usd=0.01)
        self.assertEqual(len(result), 1)

    def test_accepts_variant_duration(self):
        result = filter_events([{"latency_ms": 300}], min_duration_ms=200)
        self.assertEqual(len(result), 1)

    def test_numeric_cost_as_string_is_coerced(self):
        # Values stored as strings should still be comparable numerically.
        result = filter_events([{"cost_usd": "0.03"}], min_cost_usd=0.01)
        self.assertEqual(len(result), 1)

    def test_empty_string_error_is_not_an_error(self):
        # A falsy error field means "no error".
        result = filter_events([{"error": ""}], has_error=False)
        self.assertEqual(len(result), 1)


class EventFilterChainTests(unittest.TestCase):
    def test_chain_kind(self):
        self.assertEqual(len(EventFilter(EVENTS).where_kind("llm_call").result()), 3)

    def test_chain_model(self):
        self.assertEqual(
            len(EventFilter(EVENTS).where_model("claude-sonnet-4-5").result()), 3
        )

    def test_chain_no_error(self):
        self.assertEqual(len(EventFilter(EVENTS).where_no_error().result()), 4)

    def test_chain_has_error(self):
        self.assertEqual(len(EventFilter(EVENTS).where_has_error().result()), 1)

    def test_chain_cost(self):
        self.assertGreaterEqual(
            len(EventFilter(EVENTS).where_cost(min=0.005).result()), 1
        )

    def test_chain_duration(self):
        self.assertGreaterEqual(
            len(EventFilter(EVENTS).where_duration(max=100).result()), 1
        )

    def test_chain_combined(self):
        result = (
            EventFilter(EVENTS)
            .where_kind("llm_call")
            .where_no_error()
            .result()
        )
        self.assertEqual(len(result), 2)

    def test_count_and_len(self):
        f = EventFilter(EVENTS).where_kind("llm_call")
        self.assertEqual(f.count(), 3)
        self.assertEqual(len(f), 3)

    def test_iterable(self):
        events = list(EventFilter(EVENTS).where_kind("llm_call"))
        self.assertEqual(len(events), 3)

    def test_where_custom(self):
        result = EventFilter(EVENTS).where(lambda e: e.get("cost_usd", 0) > 0.015).result()
        self.assertEqual(len(result), 1)

    def test_multiple_kinds(self):
        result = EventFilter(EVENTS).where_kind("llm_call", "tool_call").result()
        self.assertEqual(len(result), 5)

    def test_timestamp(self):
        result = EventFilter(EVENTS).where_timestamp(after=1020, before=1030).result()
        self.assertEqual(len(result), 2)

    def test_constructor_copies_input(self):
        # Mutating the source list after construction must not affect the filter.
        src = list(EVENTS)
        f = EventFilter(src)
        src.append({"kind": "extra"})
        self.assertEqual(f.count(), 5)

    def test_result_returns_copy(self):
        f = EventFilter(EVENTS)
        out = f.result()
        out.append({"kind": "mutated"})
        self.assertEqual(f.count(), 5)


class FilterFileTests(unittest.TestCase):
    def _write_jsonl(self, lines):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(lines)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def test_basic(self):
        path = self._write_jsonl("\n".join(json.dumps(e) for e in EVENTS) + "\n")
        result = filter_file(path, kind="llm_call")
        self.assertEqual(len(result), 3)

    def test_with_dest(self):
        src = self._write_jsonl(json.dumps(EVENTS[0]) + "\n")
        fd, dst = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(dst) and os.remove(dst))
        filter_file(src, dst)
        with open(dst, encoding="utf-8") as fh:
            written = [json.loads(line) for line in fh.read().splitlines() if line.strip()]
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0], EVENTS[0])

    def test_skips_blank_lines(self):
        path = self._write_jsonl(
            json.dumps(EVENTS[0]) + "\n\n" + json.dumps(EVENTS[1]) + "\n"
        )
        result = filter_file(path)
        self.assertEqual(len(result), 2)

    def test_skips_malformed_lines(self):
        # Invalid JSON lines should be skipped, not raise.
        path = self._write_jsonl(
            json.dumps(EVENTS[0]) + "\n" + "{not valid json}\n" + json.dumps(EVENTS[1]) + "\n"
        )
        result = filter_file(path)
        self.assertEqual(len(result), 2)

    def test_accepts_path_object(self):
        from pathlib import Path

        path = self._write_jsonl(json.dumps(EVENTS[0]) + "\n")
        result = filter_file(Path(path))
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
