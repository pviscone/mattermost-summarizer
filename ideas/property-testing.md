# Property-Based Testing with Hypothesis

Exploration of adding or migrating to property-based testing using [Hypothesis](https://hypothesis.readthedocs.io/).

## Current state

- 46 example-based tests across 5 files (pytest)
- No property-based, generative, or fuzzing tests
- `hypothesis` is not yet a dependency
- `respx` is a dev dependency but unused — a consolidation candidate

```
tests/
├── test_models.py          17 tests  — Pydantic model construction/formatting
├── test_parse_permalink.py  8 tests  — URL parsing
├── test_config.py           5 tests  — Config/env vars
├── test_client.py           9 tests  — HTTP mocking (pytest-httpserver)
└── test_tools.py            7 tests  — Tool observations
```

---

## Where property-based testing would add value

### Tier 1: Pure functions (highest ROI, zero setup cost)

These have crystal-clear invariants and no external dependencies.

| Target | Invariant |
|--------|-----------|
| `_format_token_count(n)` | `n >= 1000` → result ends with `"K"` |
| | `n < 1000` → result equals `str(n)` |
| | `n >= 0` → result is parseable back to a number |
| `_inline_bold(s)` | Output contains zero `**` substrings |
| | All text outside `**...**` is preserved |
| | Idempotent: applying twice gives the same result |
| `parse_permalink(url)` | Valid pattern `{scheme}://{host}/{team}/pl/{id}` → returns `id` |
| | Any format deviation → raises `PermalinkError` |
| | Empty, schemeless, or garbage → raises `PermalinkError` |

Edge cases that example tests miss today:

```python
_format_token_count(-1)            # negative? type error? undefined?
_format_token_count(0)             # boundary
_inline_bold("**unclosed")         # unclosed marker — output contains "**"?
_inline_bold("****")               # empty bold span
_inline_bold("***triple***")       # triple asterisk
parse_permalink("https://x.com/pl/")          # empty post ID
parse_permalink("https://x.com/team/pl/abc?q=1")  # query params
parse_permalink("HTTPS://X.COM/TEAM/PL/ABC")  # uppercase scheme
```

### Tier 2: Pydantic model invariants

Hypothesis has first-class Pydantic support via `st.builds()`.

```python
# PostData
post.reply_count >= 0
post.reactions is a list
post.created_at is not None

# PostThread
len(thread.replies) == thread.total_replies  (structural consistency)
thread.root is a valid PostData

# SummaryMeta — all numeric fields are non-negative
cost >= 0.0
duration_seconds >= 0.0
input_tokens, output_tokens, cache_*_tokens, reasoning_tokens >= 0

# Channel
type in {"O", "P", "D", "G"}
```

### Tier 3: Consistency / round-trip properties

| Property | What it checks |
|----------|----------------|
| `__str__()` vs `render_rich()` | Both contain the same semantic content (same TL;DR, key findings, participants) |
| `parse_permalink` round-trip | Build a URL from known parts → parse it → recover the same ID |
| `get_user(id)` idempotency | Two calls return structurally equal data; second call makes zero HTTP requests |
| Tool observations | `to_llm_content` always returns a non-empty list with the expected structure |

---

## Migration options

### Option A — Light touch (additive only)

Add Hypothesis alongside existing tests. No existing tests are modified.

**Steps:**
1. `uv add hypothesis --dev`
2. Write property tests for `_format_token_count`, `_inline_bold`, `parse_permalink`
3. Write property tests for model invariants (`PostData`, `PostThread`, `SummaryMeta`)

**Effort:** ~2 hours, zero refactoring risk.

**Pro:** Instant payoff; catches edge cases no one thought to cover.  
**Con:** Two testing styles coexist; some conceptual overlap with existing example tests.

---

### Option B — Gradual migration (recommended long-term)

Start with Option A, then progressively replace model example tests with Hypothesis strategies where coverage overlaps.

**Additional steps beyond Option A:**
1. Replace `TestPostData`, `TestUserProfile`, `TestChannel` example-construction tests with `@given(st.builds(...))` strategies
2. Keep rendering/formatting tests as examples — they check visual output that doesn't generalise well
3. Add round-trip property: `__str__()` and `render_rich()` contain the same semantic content
4. Add `parse_permalink` round-trip: generate valid URLs → parse → recover ID

**Effort:** ~6 hours spread over time.

**Pro:** Fewer lines of test code covering more scenarios; Pydantic + Hypothesis is low boilerplate.  
**Con:** Requires designing good Hypothesis strategies; more upfront thinking.

---

### Option C — Full property-based coverage

Extends Option B with:
- Stateful testing of `MattermostClient` (generate sequences of API calls, model caching and error behaviour)
- Fuzz tool observation formatting with extreme/adversarial inputs
- Verify all `to_llm_content` outputs meet structural contracts across generated observations

**Effort:** ~12+ hours.

**Pro:** Extremely thorough; models the system as a state machine.  
**Con:** Overkill for the current size of the project (~2k LOC, 46 tests).

---

## What the tests would look like

### Pure functions

```python
from hypothesis import given, assume
from hypothesis import strategies as st
import pytest
from mattermost_summarizer.models import _format_token_count
from mattermost_summarizer.utils import parse_permalink, PermalinkError

@given(st.integers(min_value=0, max_value=10_000_000))
def test_format_token_count_large(n):
    result = _format_token_count(n)
    if n >= 1000:
        assert result.endswith("K")
        assert float(result[:-1]) > 0
    else:
        assert result == str(n)

@given(st.text())
def test_inline_bold_no_asterisks_in_output(s):
    from mattermost_summarizer.models import _inline_bold
    result = _inline_bold(s)
    assert "**" not in result.plain

@given(st.text())
def test_parse_permalink_non_http_raises(url):
    assume(not url.lower().startswith("http"))
    with pytest.raises(PermalinkError):
        parse_permalink(url)
```

### Model invariants

```python
from hypothesis import given
from hypothesis import strategies as st
from hypothesis.extra.pydantic import from_type  # or st.builds()
from mattermost_summarizer.models import SummaryMeta

@given(st.builds(
    SummaryMeta,
    cost=st.floats(min_value=0.0, allow_nan=False),
    duration_seconds=st.floats(min_value=0.0, allow_nan=False),
    input_tokens=st.integers(min_value=0),
    output_tokens=st.integers(min_value=0),
    cache_read_tokens=st.integers(min_value=0),
    cache_write_tokens=st.integers(min_value=0),
    reasoning_tokens=st.integers(min_value=0),
))
def test_summary_meta_all_fields_non_negative(meta):
    assert meta.cost >= 0.0
    assert meta.duration_seconds >= 0.0
    assert meta.input_tokens >= 0
    assert meta.output_tokens >= 0
```

---

## Implementation notes

- Hypothesis stores a database of failing examples in `.hypothesis/` — add this to `.gitignore` or commit it to persist shrunk counterexamples across runs
- Hypothesis plays well with `pytest` — no separate test runner needed
- The `hypothesis.extra.pydantic` extras package provides `from_type()` for auto-generating Pydantic model instances without manual `st.builds()` calls
- `@settings(max_examples=200)` can increase thoroughness for critical functions at the cost of test runtime
- Hypothesis can be [integrated with CI](https://hypothesis.readthedocs.io/en/latest/details.html#use-with-external-fuzzers) for continuous fuzzing
