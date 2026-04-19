# Stage demo — speaker notes (Gittan)

**Audience:** Large room · **Tone:** Same as root [`README.md`](../../README.md) — clear, confident, not salesy.

## Three sentences (read or paraphrase)

**Gittan** turns the messy signals you already leave on your machine—IDE, browser, mail, commits, worklog—into **honest hours** and review-ready output, without shipping your raw day to our cloud by default. It is **local-first** by design: you choose sources, you keep the files, and you can export JSON or PDF when someone asks for proof. If you want to try it after this talk, install is one line with **pipx** or **pip**; optional **Homebrew** install is documented for maintainers setting up a tap.

## One-liner installs (show on slide or terminal)

```bash
pipx install timelog-extract && gittan -V
```

Optional (if your Homebrew tap is live):

```bash
brew tap <your-github>/gittan && brew install gittan && gittan -V
```

Details: [`docs/runbooks/homebrew-tap.md`](../runbooks/homebrew-tap.md).

## If something breaks on stage

- Fall back to **PyPI + pipx** — always matches what’s published.  
- Say: *“Full setup and collectors are in the repo README and `gittan doctor`.”*
