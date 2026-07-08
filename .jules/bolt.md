## 2026-07-06 - [Project Classification Optimization]
**Learning:** Project classification `classify_project` was a hot path because it iterated over many profiles and match terms for every single event. Alphanumeric word-boundary matching with `re.search(rf"\b{re.escape(clean)}\b", ...)` is expensive when called thousands of times. Normalizing all terms and using a pre-calculated `word_set` for O(1) membership check is significantly faster and maintains same semantics. Local `match_cache` per `classify_project` call prevents re-evaluating the same term across different profiles.
**Action:** Use set-based word lookups for alphanumeric word-boundary enforcement in high-frequency text classification tasks. Ensure all profile terms are normalized (lowercased/stripped) once and cached.

## 2026-07-08 - [Classification Engine Refinement]
**Learning:** Even with set-based lookups, redundant passes over large profile lists in  add measurable overhead. Consolidating "caching" and "ranking" into a single lazy pass reduces total iterations. Additionally, caching *negative* results in the local  is critical; otherwise, substring checks are re-run for every profile that shares a non-matching term.
**Action:** Use single-pass lazy evaluation for matching/ranking in hot paths. Ensure local caches explicitly store negative results to prevent redundant expensive checks.

## 2026-07-08 - [Classification Engine Refinement]
**Learning:** Even with set-based lookups, redundant passes over large profile lists in `classify_project` add measurable overhead. Consolidating "caching" and "ranking" into a single lazy pass reduces total iterations. Additionally, caching *negative* results in the local `match_cache` is critical; otherwise, substring checks are re-run for every profile that shares a non-matching term.
**Action:** Use single-pass lazy evaluation for matching/ranking in hot paths. Ensure local caches explicitly store negative results to prevent redundant expensive checks.
