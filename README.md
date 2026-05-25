# trace-event-filter

Filter agent JSONL trace events by field values. Zero dependencies.

## Install

```bash
pip install trace-event-filter
```

## Usage

```python
from trace_event_filter import filter_events, EventFilter, filter_file

# Functional
llm_errors = filter_events(events, kind="llm_call", has_error=True)
expensive = filter_events(events, min_cost_usd=0.01)

# Chainable
result = (
    EventFilter(events)
    .where_kind("llm_call")
    .where_no_error()
    .where_cost(min=0.001, max=0.05)
    .result()
)

# From JSONL file
result = filter_file("traces.jsonl", kind="llm_call", has_error=False)
```

## Zero dependencies

Standard library only: `json`, `pathlib`. Nothing else.
