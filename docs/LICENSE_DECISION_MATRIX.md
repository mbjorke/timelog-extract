# License decision matrix (stop overthinking)

**Goal in one line:** keep **credit and/or money** in play, without pretending the choices are perfect. This table compares **common licenses** to **what you have now** (Gittan / Timelog Extract License + `SPONSORSHIP_TERMS.md`).

**Not legal advice.** Use for intuition; a lawyer validates anything business-critical.

## Legend

- **Strong / yes** — fits that row well  
- **Partial** — sometimes, or “it depends”  
- **Weak / no** — does not fit that row  

## Matrix

| Criterion | MIT | Apache-2.0 | AGPL-3.0 | Elastic License 2.0 *(style)* | **Gittan (current)** |
|-----------|-----|------------|----------|--------------------------------|----------------------|
| **Lets big companies use & modify commercially without paying you** | Strong yes | Strong yes | Weaker — copyleft + network obligations on many SaaS-style uses | Weaker for *hosting the same product as a competing managed service*; **internal use** often still allowed | **No** for *scale* use — sponsorship tier required past small team (see `SPONSORSHIP_TERMS.md`) |
| **Puts money on the table without a separate contract** | Weak | Weak | Weak | Weak | **Strong** — Patreon / tier mapping |
| **“Street cred” / familiar to developers & hiring** | Strong | Strong | Mixed (some firms avoid AGPL) | Low — people think “Elasticsearch drama”, not your app | **Partial** — fine if README explains it once (`LICENSE_GOALS.md`) |
| **Simple for others to reuse in closed products** | Strong | Strong | Weak | Partial | Weak for *large teams*; OK for small-team / personal |
| **Forces competitors to open their changes** | Weak | Weak | Strong | Partial (ELv2 is product-specific) | Weak — not copyleft |
| **Explicit patent grant (comfort for users)** | Weak | Strong | Yes (GPL family) | Varies | Not the focus of your license |
| **You can change terms on future releases** | Partial (old copies stay MIT) | Partial | Partial | Partial | **Yes** — stated in `LICENSE` |
| **Mental load / “did I overthink this?”** | Low | Low | High | High | **Medium** — one custom story, document it once |

## One-line verdicts

- **MIT / Apache** — Best for **maximum reuse and zero explanation**. Worst for **automatic money from big teams** (Apache adds **patent** clarity vs MIT).  
- **AGPL** — Best for **“freedom of the commons”** and **SaaS copyleft** in spirit; awkward for **your Patreon-by-team-size** model without **dual licensing**.  
- **Elastic-style (ELv2)** — Built for **“don’t compete with our hosted product”** on **that** product; **not** the same problem as **“pay me for team size.”**  
- **Gittan (current)** — Best **fit for money from scale use + company ownership**; pay the **README one-liner** so it still feels **serious** on LinkedIn.

## If you only remember one thing

You said you want **cred or money**, not to **feel** you gave everything to Google for free. **MIT/Apache** maximize adoption and **hireability**; they do **not** maximize **payment from large orgs**. **Your current license** is the odd one that actually encodes **“bigger use → sponsor.”** Keep it **and** keep the explanation short — that’s the anti-overthinking move.
