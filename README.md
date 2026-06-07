# trace-event-filter

Filter agent JSONL trace events by field values. Zero dependencies.

Agent and LLM tracing tools emit one JSON object per line (JSONL): an `llm_call`,
a `tool_call`, an error, and so on. `trace-event-filter` lets you slice those
event streams by **kind**, **model**, **error presence**, and **cost / duration /
timestamp ranges** — or with an arbitrary predicate — using either a simple
function call or a chainable builder. It reads the canonical field names emitted by
[`trace-field-normalize`](https://github.com/MukundaKatta) and also tolerates the
common variants different tools use (`event_type`, `ts`, `latency_ms`, `err`, ...).

## Install

```bash
pip install trace-event-filter
```

Requires Python 3.10+. No third-party dependencies.

## Usage

```python
from trace_event_filter import filter_events, EventFilter, filter_file

events = [
    {"kind": "llm_call",  "model": "claude-sonnet-4-5", "cost_usd": 0.012, "duration_ms": 240},
    {"kind": "tool_call", "model": "claude-sonnet-4-5", "cost_usd": 0.001, "duration_ms": 30},
    {"kind": "llm_call",  "model": "gpt-5.4",           "cost_usd": 0.020, "error": "timeout"},
]

# Functional: pass any combination of filters as keyword arguments.
llm_errors = filter_events(events, kind="llm_call", has_error=True)
expensive  = filter_events(events, min_cost_usd=0.01)

# Chainable: build a filter step by step.
result = (
    EventFilter(events)
    .where_kind("llm_call")
    .where_no_error()
    .where_cost(min=0.001, max=0.05)
    .result()
)

# From a JSONL file (optionally write the matches to another file).
matches = filter_file("traces.jsonl", kind="llm_call", has_error=False)
filter_file("traces.jsonl", "errors.jsonl", has_error=True)
```

Every filter argument is optional. Passing no filters returns all events. Filters
are combined with logical AND — an event must satisfy all of them to be kept.

### Tolerated field-name variants

A filter matches whichever of these keys is present on an event:

| Concept   | Keys checked (in order)                                   |
| --------- | -------------------------------------------------------- |
| kind      | `kind`, `event_type`, `type`, `event_kind`               |
| model     | `model`, `model_id`, `model_name`                        |
| error     | `error`, `err`, `exception`, `error_message`             |
| cost      | `cost_usd`, `cost`, `price_usd`                          |
| duration  | `duration_ms`, `latency_ms`, `elapsed_ms`               |
| timestamp | `timestamp`, `ts`, `time`, `created_at`, `event_time`    |

Numeric values stored as strings (for example `{"cost_usd": "0.03"}`) are coerced
to floats before comparison. Events that lack the relevant field never satisfy a
numeric range filter.

## API

### `filter_events(events, *, kind=None, model=None, has_error=None, min_cost_usd=None, max_cost_usd=None, min_duration_ms=None, max_duration_ms=None, after_ts=None, before_ts=None, where=None) -> list[dict]`

Filter a list of event dicts and return a **new** list of the matches (the input
list and its dicts are never mutated).

- `kind` / `model` — keep events matching a single value (`str`) or any of several
  (`list[str]`).
- `has_error` — `True` keeps only error events, `False` keeps only non-error
  events, `None` ignores the field.
- `min_cost_usd` / `max_cost_usd` — inclusive cost bounds in USD.
- `min_duration_ms` / `max_duration_ms` — inclusive duration bounds in milliseconds.
- `after_ts` / `before_ts` — inclusive timestamp bounds (Unix epoch).
- `where` — a custom `Callable[[dict], bool]` for arbitrary filtering.

### `filter_file(source, dest=None, **kwargs) -> list[dict]`

Load a JSONL file from `source` (a path string or `pathlib.Path`), filter it with
the same keyword arguments as `filter_events`, and return the matches. Blank lines
and lines that are not valid JSON are skipped. If `dest` is given, the matching
events are also written to that path as JSONL.

### `class EventFilter(events)`

A chainable wrapper around `filter_events`. Each `where_*` method returns a **new**
`EventFilter`, so chains are side-effect free.

| Method                                   | Effect                                        |
| ---------------------------------------- | --------------------------------------------- |
| `.where_kind(*kinds)`                    | keep events of any given kind                 |
| `.where_model(*models)`                  | keep events of any given model                |
| `.where_has_error()`                     | keep only error events                        |
| `.where_no_error()`                      | keep only non-error events                    |
| `.where_cost(min=None, max=None)`        | keep events within a cost range               |
| `.where_duration(min=None, max=None)`    | keep events within a duration range           |
| `.where_timestamp(after=None, before=None)` | keep events within a timestamp range       |
| `.where(fn)`                             | keep events for which `fn(event)` is truthy   |
| `.result()`                              | return the current events as a `list[dict]`   |
| `.count()` / `len(filter)`               | number of events currently matched            |
| `iter(filter)`                           | iterate over the current events               |

## Development

Run the test suite with the standard library only — no test runner to install:

```bash
python3 -m unittest discover -s tests
```

## Zero dependencies

Standard library only: `json`, `pathlib`. Nothing else.

## License

MIT — see [LICENSE](LICENSE).
