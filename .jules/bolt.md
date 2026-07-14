## 2026-07-06 - [Project Classification Optimization]
**Learning:** Project classification `classify_project` was a hot path because it iterated over many profiles and match terms for every single event. Alphanumeric word-boundary matching with `re.search(rf"\b{re.escape(clean)}\b", ...)` is expensive when called thousands of times. Normalizing all terms and using a pre-calculated `word_set` for O(1) membership check is significantly faster and maintains same semantics. Local `match_cache` per `classify_project` call prevents re-evaluating the same term across different profiles.
**Action:** Use set-based word lookups for alphanumeric word-boundary enforcement in high-frequency text classification tasks. Ensure all profile terms are normalized (lowercased/stripped) once and cached.

## 2026-07-08 - [Classification Engine Refinement]
**Learning:** Even with set-based lookups, redundant passes over large profile lists in `classify_project` add measurable overhead. Consolidating "caching" and "ranking" into a single lazy pass reduces total iterations. Additionally, caching *negative* results in the local `match_cache` is critical; otherwise, substring checks are re-run for every profile that shares a non-matching term.
**Action:** Use single-pass lazy evaluation for matching/ranking in hot paths. Ensure local caches explicitly store negative results to prevent redundant expensive checks.

## 2026-07-09 - [Inverted Index for Project Classification]
**Learning:** Project classification was the primary bottleneck because it performed O(N*M) matching (Profiles * Terms) for every event. Moving to an inverted index allows O(U) matching (Unique words in event) for alphanumeric terms. Set intersection between the event's word set and the "fast path" index identifies matches instantly.
**Action:** Use inverted indices for many-to-many matching tasks. Always separate "fast path" (exact/word set) and "slow path" (regex/substring) to minimize expensive operations.

## 2026-07-14 - [WorkUnit v2 Inverted Index Optimization]
**Learning:** The WorkUnit v2 spike classifier was suffering from the same O(N*M) bottleneck as the original v1 classifier. Even though it's a "spike", performance matters for large event sets. Applying the inverted index pattern (from 2026-07-09) and using sparse dictionaries for scoring instead of full-sized lists further optimizes memory and time when many units have zero matches.
**Action:** Always apply the inverted index pattern to text-to-profile classification tasks. Use dictionaries for sparse scoring to avoid O(N) work for non-matching profiles.
