# License decision matrix (stop overthinking)

**Goal in one line:** keep **open-source clarity** while protecting long-term project sustainability. This table compares common options and records why GPL-3.0-or-later is the chosen path.

**Not legal advice.** Use for intuition; a lawyer validates anything business-critical.

## Legend

- **Strong / yes** — fits that row well  
- **Partial** — sometimes, or “it depends”  
- **Weak / no** — does not fit that row  

## Matrix

| Criterion | MIT | Apache-2.0 | AGPL-3.0 | Elastic License 2.0 *(style)* | **GPL-3.0-or-later (current)** |
|-----------|-----|------------|----------|--------------------------------|----------------------|
| **Lets big companies use & modify commercially without paying you** | Strong yes | Strong yes | Weaker — copyleft + network obligations on many SaaS-style uses | Weaker for *hosting the same product as a competing managed service*; **internal use** often still allowed | Strong yes (under GPL obligations) |
| **Puts money on the table without a separate contract** | Weak | Weak | Weak | Weak | Weak (license is open-source; funding is voluntary) |
| **“Street cred” / familiar to developers & hiring** | Strong | Strong | Mixed (some firms avoid AGPL) | Low — people think “Elasticsearch drama”, not your app | **Partial** — fine if README explains it once (`LICENSE_GOALS.md`) |
| **Simple for others to reuse in closed products** | Strong | Strong | Weak | Partial | Weak (copyleft) |
| **Forces competitors to open their changes** | Weak | Weak | Strong | Partial (ELv2 is product-specific) | Weak — not copyleft |
| **Explicit patent grant (comfort for users)** | Weak | Strong | Yes (GPL family) | Varies | Not the focus of your license |
| **You can change terms on future releases** | Partial (old copies stay MIT) | Partial | Partial | Partial | Partial (old copies remain GPL) |
| **Mental load / “did I overthink this?”** | Low | Low | High | High | **Medium** — one custom story, document it once |

## One-line verdicts

- **MIT / Apache** — Best for **maximum reuse and zero explanation**. Worst for **automatic money from big teams** (Apache adds **patent** clarity vs MIT).  
- **AGPL** — Best for **“freedom of the commons”** and **SaaS copyleft** in spirit; awkward for **your Patreon-by-team-size** model without **dual licensing**.  
- **Elastic-style (ELv2)** — Built for **“don’t compete with our hosted product”** on **that** product; **not** the same problem as **“pay me for team size.”**  
- **GPL-3.0-or-later (current)** — Best fit for standard open-source expectations plus reciprocity via copyleft.

## If you only remember one thing

GPL-3.0-or-later is the current project license. Keep documentation explicit and consistent so users understand the open-source/copyright model without mixed legacy wording.
