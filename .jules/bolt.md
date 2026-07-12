## 2026-07-06 - [Project Classification Optimization]
**Learning:** Project classification `classify_project` was a hot path because it iterated over many profiles and match terms for every single event. Alphanumeric word-boundary matching with `re.search(rf"\b{re.escape(clean)}\b", ...)` is expensive when called thousands of times. Normalizing all terms and using a pre-calculated `word_set` for O(1) membership check is significantly faster and maintains same semantics. Local `match_cache` per `classify_project` call prevents re-evaluating the same term across different profiles.
**Action:** Use set-based word lookups for alphanumeric word-boundary enforcement in high-frequency text classification tasks. Ensure all profile terms are normalized (lowercased/stripped) once and cached.

## 2026-07-08 - [Classification Engine Refinement]
**Learning:** Even with set-based lookups, redundant passes over large profile lists in `classify_project` add measurable overhead. Consolidating "caching" and "ranking" into a single lazy pass reduces total iterations. Additionally, caching *negative* results in the local `match_cache` is critical; otherwise, substring checks are re-run for every profile that shares a non-matching term.
**Action:** Use single-pass lazy evaluation for matching/ranking in hot paths. Ensure local caches explicitly store negative results to prevent redundant expensive checks.

## 2026-07-09 - [Inverted Index for Project Classification]
**Learning:** Project classification was the primary bottleneck because it performed O(N*M) matching (Profiles * Terms) for every event. Moving to an inverted index allows O(U) matching (Unique words in event) for alphanumeric terms. Set intersection between the event's word set and the "fast path" index identifies matches instantly.
**Action:** Use inverted indices for many-to-many matching tasks. Always separate "fast path" (exact/word set) and "slow path" (regex/substring) to minimize expensive operations.

## 2026-07-12 - [WorkUnit Classification Optimization]
**Learning:** The `WorkUnit` classification (v2 spike) was still using O(N*M) matching per event. Applying the same inverted index pattern used in `core/domain.py` reduced classification time from ~2.6ms to ~0.2ms per event (~13x speedup). Caching the compiled index with a fingerprint `(len(units), tuple((u.line_key, len(u.signals)) for u in units))` safely handles potential in-place mutations of `WorkUnit` objects while avoiding redundant indexing.
**Action:** Consistently apply the inverted index pattern (fast-path word set + slow-path substring) for any many-to-one signal classification tasks.
