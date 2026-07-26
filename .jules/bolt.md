## 2026-07-06 - [Project Classification Optimization]
**Learning:** Project classification `classify_project` was a hot path because it iterated over many profiles and match terms for every single event. Alphanumeric word-boundary matching with `re.search(rf"\b{re.escape(clean)}\b", ...)` is expensive when called thousands of times. Normalizing all terms and using a pre-calculated `word_set` for O(1) membership check is significantly faster and maintains same semantics. Local `match_cache` per `classify_project` call prevents re-evaluating the same term across different profiles.
**Action:** Use set-based word lookups for alphanumeric word-boundary enforcement in high-frequency text classification tasks. Ensure all profile terms are normalized (lowercased/stripped) once and cached.

## 2026-07-08 - [Classification Engine Refinement]
**Learning:** Even with set-based lookups, redundant passes over large profile lists in `classify_project` add measurable overhead. Consolidating "caching" and "ranking" into a single lazy pass reduces total iterations. Additionally, caching *negative* results in the local `match_cache` is critical; otherwise, substring checks are re-run for every profile that shares a non-matching term.
**Action:** Use single-pass lazy evaluation for matching/ranking in hot paths. Ensure local caches explicitly store negative results to prevent redundant expensive checks.

## 2026-07-09 - [Inverted Index for Project Classification]
**Learning:** Project classification was the primary bottleneck because it performed O(N*M) matching (Profiles * Terms) for every event. Moving to an inverted index allows O(U) matching (Unique words in event) for alphanumeric terms. Set intersection between the event's word set and the "fast path" index identifies matches instantly.
**Action:** Use inverted indices for many-to-many matching tasks. Always separate "fast path" (exact/word set) and "slow path" (regex/substring) to minimize expensive operations.

## 2026-07-16 - [WorkUnit Classification Inverted Index]
**Learning:** The WorkUnit v2 spike classifier had a similar performance bottleneck to the original project classifier because it iterated over all units and signals sequentially for every text snippet. Compiling an inverted index that maps signals to pre-calculated weights and properties (categorized into fast-path alphanumeric and slow-path path/regex signals) reduces classification cost from O(U*S) to roughly O(min(words, fast signals) + slow signals + matched impacts).
**Action:** Use inverted indices with fast/slow signal paths for WorkUnit classification. Cache compiled indexes with identity **and** content fingerprint (same pattern as `domain._get_compiled_index`). Never use an identity-only early return on mutable sequences — that reintroduces stale-index bugs and has already been reverted once after review (#386 follow-up).

## 2026-07-17 - [Do not reopen solved Bolt work / check open PRs first]
**Learning:** Opening a fresh PR every day for the same Bolt task (WorkUnit inverted index) produced seven near-duplicate PRs (#374–#386). After #386 merged, a follow-up commit reintroduced an identity-only cache fast path that review had just removed, and deleted the regression test — undoing a correctness fix. Qodo and CodeRabbit had already flagged that exact stale-cache issue; the revert ignored them.
**Action:** Follow `docs/contributing/jules-standing-instructions.md` before every Bolt run: (1) list open PRs (GitHub UI — do not assume `gh`) and do not duplicate, (2) read Qodo + CodeRabbit threads on matching PRs and fix or respect them, (3) never revert a review fix or delete its regression test unless the PR thread explicitly asks, (4) when comments are addressed and CI is green, **finish the PR** (§5: merge in GitHub UI if allowed, else ready-to-merge comment) instead of leaving it for tomorrow’s brief to duplicate.

## 2026-07-19 - [Optimize Log Timestamp Parsing via fromisoformat]
**Learning:** Parsing timestamps from massive IDE diagnostic and always-local logs is highly frequent in Gittan's collectors. Using `datetime.strptime` on every line is a significant CPU bottleneck. Switching to `datetime.fromisoformat` after slicing to 26 characters (to handle space separators and cap at microseconds) yields a ~4.4x to 6.0x speedup for parsing log timestamps.
**Action:** Prefer `datetime.fromisoformat` over `datetime.strptime` for parsing ISO-like log timestamps in performance-sensitive I/O loops. Slice timezone-naive/millisecond strings to at most 26 characters to safely handle microsecond limits.

## 2026-07-21 - [Optimize Date and Timestamp Parsing in Core & git_activity_discovery]
**Learning:** Parsing simple ISO dates (like `YYYY-MM-DD` and `YYYY-MM-DD HH:MM:SS`) in hot paths (such as `core/analytics.py` date-range setup and `core/git_activity_discovery.py` Cursor log scanning) was using `datetime.strptime`, which parses strings via expensive regex and locale compilation. Switching to `datetime.fromisoformat` provides a ~32.7x to 37.1x micro-benchmark speedup, and decreases hotpath report compilation times noticeably.
**Action:** Always prefer `datetime.fromisoformat` over `datetime.strptime` for standard ISO-8601 date and time parsing across core utilities and collectors alike.

## 2026-07-22 - [Optimize group_by_day Aggregation Phase]
**Learning:** Aggregating large datasets into local day groups inside `core/analytics.py`'s `group_by_day` is highly frequent. For every event, it was performing unnecessary dictionary and string operations for detail parsing (even with no exclude keywords set), allocating a full `datetime.date` object, and converting it to an ISO string. Lazy-evaluating the detail string only if exclude keywords are set, caching the `local_ts.date().isoformat()` conversions via a year/month/day tuple comparison across contiguous events, and using shallow copies instead of dictionary unpacking yields a ~1.74x speedup on report grouping.
**Action:** For sequential grouping loops over chronological datasets, use a micro-cache/sliding window of the last seen date component keys to bypass date formatting and object instantiation. Always conditionally evaluate string/dictionary lookups that are only needed for filtering under active option flags.

## 2026-07-23 - [Optimize Cursor Log Day Dir Parsing]
**Learning:** In Cursor log scanning (`collectors/cursor_log_scan.py`), parsing the day directory (e.g. `20260709T162324`) using `datetime.strptime` on every launch folder in the user's logs directory is exceptionally slow because `strptime` dynamically parses formats, sets locales, and compiles regexes.
**Action:** Use manual integer conversion of sliced string components with `datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))` to achieve a ~11.6x speedup over `datetime.strptime(..., "%Y%m%d").date()`.
