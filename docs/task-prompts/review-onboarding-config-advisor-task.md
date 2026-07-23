# Review / onboarding config-advisor track

Product-owner backlog for making **`gittan review` + setup mapping** a trustworthy
onboarding path: create when decidable, park when not, remotes parity with setup,
and honest write messaging — without forcing undecidable Lovable UUID phantoms.

Framing: [`docs/product/vision-documents.md`](../product/vision-documents.md) →
local-first, proof over theater, reduce cognitive load (`gittan-vision.md`).
Adjacent shipped guidance: [`project-config-onboarding-guidance-task.md`](project-config-onboarding-guidance-task.md)
(GH-197). Customer-first map UX historically in
[`map-customer-first-flow.md`](map-customer-first-flow.md) (**superseded** / NO-GO;
direction lives under work-unit v2).

## Traceability

- story_id: GH-419
- spec_status: approved
- implementation_status: in progress
- created_at: 2026-07-23
- last_updated_at: 2026-07-23
- implementation.pr: >-
    https://github.com/mbjorke/timelog-extract/pull/449 (Part of #448),
    https://github.com/mbjorke/timelog-extract/pull/450 (create + decidability),
    https://github.com/mbjorke/timelog-extract/pull/451 (setup batch-map),
    https://github.com/mbjorke/timelog-extract/pull/452 (review remotes; Part of #419)
- implementation.branch: multi-PR (see open PRs above); this spec on
  `task/po-review-onboarding-backlog`
- implementation.commits: []
- validation.evidence: >-
    maintainer smoke on review after merge stack; unit tests in each PR;
    residual Park-only check for bare `unmapped Lovable (uuid…)` hosts
- validation.decision: conditional GO
- changelog:
  - 2026-07-23: PO pass — ordered 1–2 week backlog from live review/setup pain;
    ships vs gaps for PRs #449–#452; Park-only Lovable stance; customer-first = next.

## Epic issue

[#419](https://github.com/mbjorke/timelog-extract/issues/419) — review onboarding
unusable on a fresh config (create path, impact/decidability conflation). Related:
[#448](https://github.com/mbjorke/timelog-extract/issues/448) Lovable ambient≠authorship,
[#414](https://github.com/mbjorke/timelog-extract/issues/414) Impact 0.0 / thinning,
[#416](https://github.com/mbjorke/timelog-extract/issues/416) beta onboarding dry-run,
[#264](https://github.com/mbjorke/timelog-extract/issues/264) / GH-211 setup write safety,
[#256](https://github.com/mbjorke/timelog-extract/issues/256) customer-first map
(superseded for map-centric path).

**Closing keyword discipline:** do **not** `Closes #419` from a single slice while
remotes parity (#452) and Park-only residual verification remain. Prefer
`Part of #419` until the now-items below for this epic are verified; then close.

---

## Ordered backlog (1–2 weeks)

| # | Item | Priority | Ships in / tracker |
| --- | --- | --- | --- |
| 1 | Drop implausible Lovable UUID flood from review candidates | **now** | PR **#449** (Part of #448) |
| 2 | Create project from decidable URL + decidability ranking; Park undecidable | **now** | PR **#450** |
| 3 | New remotes Add/Map/Skip in `gittan review` (setup parity) | **now** | PR **#452** |
| 4 | Residual: bare `unmapped Lovable (uuid…)` never in decidable / main force queue | **now** | Verify after #449+#450; bug residual if still visible |
| 5 | Setup customer table dupes + batch-map stem miss | **now** | PR **#451** |
| 6 | Suggest-name normalize (hyphen↔space / empty `tracked_urls` vs existing profile) | **next** | After #452; no separate issue yet |
| 7 | Setup mid-wizard write honesty (“nothing saved” vs evidence writes) | **next** | Promote #264 / GH-211 honesty slice |
| 8 | Customer-first picker on review map-to-existing | **next** | Captured on #419; #256 superseded for map path |
| 9 | Impact hours truthful (0.0 ≠ session hours) | **now** (parallel) | #414 — not blocking #419 slices |
| 10 | Beta onboarding external dry-run | **now** (after stack) | #416 — after review track greener |
| 11 | Presence ≠ authorship / Timely Memory / work-unit v2 | **next** / spike | #327, #354, #267 |
| 12 | Full merge of setup-map + review into one surface | **later** | Same epic, not a now slice |
| 13 | Map-centric customer-first (#256 path) | **do not build yet** | Superseded by work-unit v2 direction |

### Merge order among open PRs #449–#452

1. **#449** first — noise filter; unblocks clean review smoke; Part of #448.
2. **#451** in parallel or immediately after #449 — setup-only; file-disjoint from review create/remotes.
3. **#450** next — create + decidability + Park bucket (foundation).
4. **#452** last among the four — rebase onto #450 if both touch `cli_url_mapping.py`.

Also open (adjacent, not this epic’s merge gate): **#447** IDE path noise — merge when green; does not block #419.

---

### 1. Lovable UUID flood filter

- priority: now
- problem: Implausible / nil / non-v4 UUID hosts flood `gittan review` map candidates.
- user value: Operator sees fewer ghost map nudges.
- non-goals: Full ambient≠authorship contract (#448 remainder / #327).
- acceptance:
  - Nil/max/non-v4 UUID hosts do not appear as review map candidates.
  - Plausible real v4 Lovable project UUIDs still surface when unmapped.
- validation: PR #449 autotests + maintainer spot-check of review candidates.
- dependencies: None. Lands before create/remotes for cleaner smoke.

### 2. Create from decidable URL + decidability ranking

- priority: now
- problem: Fresh config has no create path; Impact conflated with “can I decide?”.
- user value: Operator can create a prefilled project from a decidable URL row and
  write with backup; ranking prefers identity signals over Impact.
- non-goals: Waiting on #414; full work-unit v2 (#267).
- behavior:

```gherkin
Feature: Review create-project for decidable URL gaps
  Fresh configs can create profiles from evidence without forced UUID mapping.

  Scenario: Decidable candidate offers create with prefilled durable fields
    Given interactive gittan review shows a URL candidate with a human title or durable slug
    When the operator chooses + Create project and confirms
    Then a timestamped backup of the projects config is created first
    And the new profile includes tracked_urls for that URL key
    And match_terms use repo/path slug only (never session titles)

  Scenario: Undecidable bare UUID is Park/Skip only
    Given a candidate whose host/title is only an unmapped Lovable UUID with no human title or durable anchor
    When the operator reaches that row in review
    Then the row is not in the decidable force-map / create queue
    And only Park or Skip is offered — never Create or Map as a forced choice
```

- acceptance: Matches maintainer decisions on #419 (2026-07-23); PR #450 test plan.
- validation: Unit tests in #450 + smoke with `--projects-config` temp empty config.
- dependencies: Prefer #449 merged first for quieter candidate set.

### 3. New remotes in review (setup parity)

- priority: now
- problem: Unmapped git remotes appear in setup but not as first-class Add/Map/Skip in review.
- user value: Same “New remote repository” job in review without running setup.
- non-goals: Full UI merge of setup + review (later).
- behavior:

```gherkin
Feature: Review surfaces new remotes like setup
  Operators expect remotes discovered locally to be actionable in review.

  Scenario: Unmapped remote appears before URL candidates
    Given an unmapped local git remote is discoverable for the review window
    When the operator runs interactive gittan review
    Then a New remote repositories step offers Add as new project / Map to existing / Skip
    And that step runs before the URL-gap table
    And accepting Add or Map writes the projects config after a timestamped backup
```

- acceptance: PR #452 summary + deferred list; Lovable UUID parks stay out of remotes step.
- validation: Unit tests in #452 + maintainer smoke with a new clone remote.
- dependencies: Rebase after #450 if shared files conflict.

### 4. Residual — unmapped Lovable visibility (stance)

- priority: now
- problem: Maintainer still saw `unmapped Lovable (d4cc9818…)` under decidable or main
  table after Park-only intent (#450 tried).
- user value: Trust — never force a choice the evidence cannot support.
- **Product stance (canonical):** bare / undecidable Lovable UUID titles are
  **Park only** — never Map/Create as a forced decision. They must not appear in
  the decidable queue or main approval table as mappable rows. Implausible UUIDs
  are dropped (#449); plausible-but-untitled UUIDs stay Park/Skip only (#450).
- non-goals: Inventing a human name for evidence-less UUIDs; auto-map by volume.
- acceptance:
  - After #449+#450: zero bare `unmapped Lovable (<hex>…)` rows in decidable /
    bulk-apply / create-eligible lists.
  - Park / “not enough evidence” bucket may list them for awareness only.
  - If still visible in decidable/main after merge → treat as **bug residual** on
    #419/#448; fix before closing #419.
- validation: Maintainer `gittan-dev review` smoke on a window known to contain
  Lovable UUID noise (numbers/names stay out of GitHub artifacts).
- dependencies: #449 + #450 merged.

### 5. Setup customer batch-map + shared-owner table

- priority: now
- problem: Duplicate customer candidate walls; batch map misses stem-matching project.
- user value: Setup identity step maps the obvious domain↔slug without unrelated leftovers.
- non-goals: Review customer-first picker (item 8).
- acceptance: PR #451 root-cause A/B fixes.
- validation: Autotests + setup wizard retest (no live customer names in PR/docs).
- dependencies: Independent of #450/#452.

### 6. Suggest-name normalize (hyphen vs space)

- priority: next
- problem: Existing profile `lunch-connect` is not auto-suggested as “Lunch Connect”
  (hyphen vs space; empty `tracked_urls`) when remotes/create propose a name.
- user value: Map-to-existing / Add prefill hits the real profile instead of a near-dupe.
- non-goals: Full fuzzy customer search UI.
- acceptance:
  - Normalize slug/display for suggestion matching (`-`/`_`/` ` collapsed).
  - Prefer existing profile with empty or matching `tracked_urls` over creating a twin.
- validation: Unit tests on suggest/match helper + one review remotes smoke.
- dependencies: After #452 lands (same suggest surfaces).

### 7. Setup write honesty

- priority: next
- problem: Wizard copy implies “nothing saved without approval” while evidence /
  intermediate state may already be written mid-flow.
- user value: Trust — messaging matches actual disk writes.
- non-goals: Redesigning the whole setup wizard.
- acceptance:
  - Any mid-wizard write is labeled as such (what file, backup or not).
  - Final “approve” language only refers to steps that still need confirmation.
  - Aligns with GH-211 / #264 write-safety spirit (no silent merge-write of tuned config).
- validation: Manual setup walkthrough + copy audit; extend #264 if needed.
- dependencies: None blocking #419 merge stack.

### 8. Customer-first picker (review map-to-existing)

- priority: next
- problem: Map-to-existing shows a flat list of all project profiles.
- user value: Operator picks **customer**, then engagement under that customer.
- non-goals: Changing engine contract (URL still attaches to a **project** profile;
  `customer` remains a field on the profile). Do not revive superseded #256 map path.
- acceptance: Customer → filtered projects / + create; optional show `customer` on
  each choice as a cheap interim. Captured on #419 (2026-07-23 comment).
- validation: Interactive review fixture with ≥2 customers, multiple engagements.
- dependencies: After create + remotes stack; may share UX with #267 later.

### 9. Impact hours accuracy (#414)

- priority: now (parallel track — does not block #419)
- problem: Impact 0.0 on multi-event candidates (Chrome thinning / drop).
- user value: Reconcile-today numbers become trustworthy again.
- non-goals: Using Impact as onboarding sort/gate (already rejected on #419).
- acceptance: Per #414; onboarding continues to rank by decidability.
- validation: #414 tests + report/review impact spot-check.
- dependencies: None for merging #449–#452.

### 10–13. Later / spike / do not build

| Item | Priority | Notes |
| --- | --- | --- |
| #416 beta external dry-run | now after stack | Run when review create/remotes + Park residual are green |
| #327 presence≠authorship, #354 Timely Memory, #267 work-unit v2 spike | next | Spike #267 only after presence/authorship progress; full v2 = do not build yet |
| One interactive surface (setup-map ∪ review) | later | Same epic; temporary forks OK |
| #256 map-centric customer-first | do not build yet | Superseded; direction via #267 |

---

## What already ships vs still missing

| Theme | In flight | Still missing after merge |
| --- | --- | --- |
| Lovable UUID flood | #449 drops implausible hosts | Ambient open-app ≠ authorship (#448 remainder) |
| Create + decidability | #450 | Closing #419 only after remotes + Park residual verified |
| Remotes parity | #452 | Full setup↔review UI merge (later) |
| Park-only UUID | Intended in #450 | **Residual bug** if still in decidable/main — verify |
| Setup customer/batch | #451 | — |
| Hyphen/space suggest | — | Item 6 (next) |
| Customer-first picker | Comment on #419 | Item 8 (next); not #256 |
| Setup honesty | Partial GH-211 | Item 7 (next) |
| Impact 0.0 | — | #414 |

---

## Label recommendations

| Issue | Current | Recommendation |
| --- | --- | --- |
| #419 | `priority:now` | Keep **now** until create + remotes + Park residual verified |
| #448 | `priority:now` | Keep **now**; #449 is slice 1 only |
| #414 | `priority:now` | Keep **now** (parallel) |
| #416 | `priority:now` | Keep **now** but sequence *after* #419 stack smoke |
| #264 | `priority:later` | Bump to **`priority:next`** (write honesty / trust) |
| #256 | `priority:later` | Keep later / treat as superseded for map path |
| #267 / #354 / #327 | `priority:next` | Keep next; no promotion to now this week |
| #266 | `priority:do-not-build` | Keep |

---

## Non-goals (locked for this epic)

- No product feature code in the PO docs PR beyond this task-prompt.
- No forcing Map/Create on evidence-less Lovable UUID phantoms.
- No Impact-based onboarding gate.
- No implementing customer-first picker in the same batch as #450/#452.
- No committing live customer names, hours, or `match_terms` from `~/.gittan`.
