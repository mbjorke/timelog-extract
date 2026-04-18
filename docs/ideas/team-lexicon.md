# Team-lexicon (människa ↔ agent, och agent ↔ agent i framtiden)

*Exploratorisk. Humor får förekomma. Kanonregler finns fortfarande i [`AGENTS.md`](../../AGENTS.md).*

Kulturella värderingar (produkt + open source) finns i [`../brand/values.md`](../brand/values.md).

Dagliga **TIL** från underhållare (för agenter) skrivs i [`til/`](til/) — en fil per månad, se [`til/README.md`](til/README.md) och `AGENTS.md` → *Maintainer TIL*.

**Hur du formulerar uppdrag** (för att undvika feltolkning) — mönster från andra projekt, på engelska: [`../inspiration/effective-commands-for-agents.md`](../inspiration/effective-commands-for-agents.md) — *föredra tydliga meningar framför sifferabbtreviationer*.

## Liten ordlista (förkortningar, smeknamn, praktik)

Förkortningar här under är **muntliga / chat-förkortningar** i teamet, inte nya tekniska namn i CI. I kod och offentlig PR-engelska: använd ordinarie namn (CodeRabbit, GitHub, m.m.).

| Säg / skriv | Menar ofta | Kommentar / nyttoläge |
| ------------- | ---------- | -------------------- |
| **TIL** | *Today I learned* — kort “idag lärde jag mig …” | En **TIL** är en etikett på en *lärdom*, som också får finnas i den här lappen. **TIL** ska alltså *inte* vara filnamnet på hela ordlistan — då låter det som att filen bara är en dagbok. Den här filen heter **team-lexicon**; TIL bor i tabellen. |
| **CR** / **CodeRabbit** | CodeRabbit (granskar PR, kommenterar) | I utvecklarchat: “Kolla med CR efter sista push” = vänta på/tydliggör CodeRabbits feedback. |
| **kanin** / **kaninen** | CodeRabbit (mascot = hare) | *Informellt.* “Nu tuggar kaninen igen” = ny review-runda eller många nya kommentarer. (CodeRabbits riktiga kvoter: se [`AGENTS.md`](../../AGENTS.md) → *Review Cadence*.) |
| **full** vs **incremental** (CR) | `@coderabbitai full review` vs `@coderabbitai review` | *Full* = heltäckande; *incremental* = mest nytt sen sist. I chat: “Kör en full, inte snack-incremental tre gånger i rad.” Se `AGENTS.md` för bästa praxis (batcha, max 1–2 cykler/PR där det går). |
| **local CR** / **CR CLI** | `coderabbit` i terminalen | Exempel: `coderabbit review --base main --type committed` — samma *AGENTS* under *CodeRabbit CLI.* |
| **Gittan** (framtidsläge) | Produkt/ton, ev. egen *agent* som representerar timelog-extract | Tänk “om Gittan blir vår bot, kan den använda samma korta ord som vi redan använder mot människor, så bottar kör med samma nätverksspråk som teamet.” Ingen hård spec här. |

## TIL: checklista slår siffermiss

**TIL (Today I learned):** När du ber en dev-agent om “färre saker i samma commit” tänk **checklista med tydliga delmoment**, inte bokstavligen “exakt *N* uppgifter per commit” — siffror blir lätt fel fokus, medan *vad som hör till samma avsikt* är rätt styrning.

- **Bra uppmaning:** “Dela upp arbetet i 3–7 tydliga punkter; bocka av i ordning; stoppa om någon punkt sprider sig till annat scope.”
- **Bristfällig uppmaning (lätt tolkat fel):** “Max fem tasks per commit” (agenten hör *policy* istället för *ungefärlig mängd*).

## Agent ↔ agent (för framtiden, halvt på skämt, halvt effektivitet)

- **Dela korta etiketter som tabellen ovan** i en intern (eller repo) ordlista, så flera agenter samma fönster/organisation slipper omskriva *lång policy* när nån bara menar *“vi väntar på CR”*.  
- **Gittan ↔ Kaninen (meta):** när/om *vår* automatisering triggar *deras* review, är det bara *pipeline-svenska* att säga “Gittan skickar till kaninen” — så länge [`AGENTS.md`](../../AGENTS.md) sista ord om rate limits, branch policy, och *run_autotests* följas i verkligheten.

*Slutligen: visionär med osäker *formulering* = utmärkt inmatning till [task prompts](../task-prompts/) (checklistor, acceptanskriterier); märklig siffra till agent = risk för bokstavstolkning. Justera mönstret, inte ambitionen.*
