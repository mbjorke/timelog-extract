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
**Learning:** Opening a fresh PR every day for the same Bolt task (WorkUnit inverted index) produced seven near-duplicate PRs (#374–#386). After #386 merged, a follow-up commit reintroduced an identity-only cache fast path that review had just removed, and deleted the regression test — undoing a correctness fix.
**Action:** Follow `docs/contributing/jules-standing-instructions.md` before every Bolt run: list open PRs, match on title/branch, and do not open a duplicate. Never revert a review fix (or delete its regression test) unless the PR thread explicitly asks for that change.
