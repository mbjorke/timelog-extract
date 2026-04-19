# Homebrew tap for `brew install gittan` (sketch)

**Package on PyPI:** `timelog-extract` (CLI commands: `gittan`, `timelog-extract`).  
**Goal for a live demo:** one memorable install line, e.g. `brew tap <org>/gittan && brew install gittan`.

This doc is a **maintainer runbook**, not user-facing install docs (those stay in root [`README.md`](../../README.md): **pipx** / **pip** remain the supported defaults until the tap exists).

---

## Why a tap (not homebrew-core) before a deadline

| Approach | Effort | Fit for “stage in 48h” |
|----------|--------|-------------------------|
| **Your own tap** (`brew tap org/gittan`) | **~0.5–1 day** first time: repo + formula + local `brew install` test | **Yes** — you control merge and naming. |
| **`brew install gittan` via homebrew-core** | **Days–weeks**: notability, review, formula style | **Risky** — do not depend on it for a fixed talk date. |

---

## What you will create (GitHub)

1. **New public repo** (name picks up the tap URL):
   - Convention: `github.com/<you>/homebrew-gittan`  
   - Homebrew maps this to tap name **`you/gittan`** (the `homebrew-` prefix is dropped).
2. **Single formula file** in that repo:
   - Path: **`Formula/gittan.rb`**
3. **README** in the tap repo with:
   - `brew tap <you>/gittan`
   - `brew install gittan`
   - `gittan -V`

After push, users run:

```bash
brew tap <you>/gittan
brew install gittan
gittan -V
```

---

## Generate the formula (recommended: use Homebrew itself)

On a Mac with **Homebrew core** available (`brew tap homebrew/core` if needed):

1. **sdist URL + checksum** for the version you ship (match PyPI):

   ```bash
   curl -sL "https://pypi.org/pypi/timelog-extract/<VERSION>/json" | python3 -c "
   import sys, json
   j = json.load(sys.stdin)
   for u in j['urls']:
       if u['packagetype'] == 'sdist':
           print('url', u['url'])
           print('sha256', u['digests']['sha256'])
   "
   ```

2. **Scaffold a Python formula** (Homebrew fills in `resource` blocks for dependencies):

   ```bash
   brew create --python --set-name gittan "https://files.pythonhosted.org/.../timelog_extract-<VERSION>.tar.gz"
   ```

   Adjust **`desc`**, **`homepage`** (`https://gittan.sh`), and **`test`** so `gittan -V` is asserted.

3. **Validate locally**:

   ```bash
   brew install --build-from-source ./gittan.rb
   brew test gittan
   brew audit --strict --online gittan.rb
   ```

4. **Copy** the finished `gittan.rb` into `homebrew-gittan/Formula/gittan.rb`, commit, tag optional.

**Note:** PyPI package name is **`timelog-extract`**; the formula name **`gittan`** is fine — it matches the command people run.

---

## Stub in this repo

See [`packaging/homebrew/README.md`](../../packaging/homebrew/README.md) for a **non-authoritative** example and the exact **0.2.11** sdist URL/checksum snapshot used when this doc was written. Regenerate the formula with `brew create --python` before you rely on it.

---

## Presentation fallback (always works)

If the tap is not ready or the room has odd network:

- **Primary:** `pipx install timelog-extract` then `gittan -V`  
- **Optional line:** “Homebrew tap coming soon” or show the two-line `brew tap` / `brew install` if the repo is live.

---

## After the talk: releases

Each **PyPI** release (see [`versioning.md`](versioning.md)):

1. Bump version on PyPI.
2. Update `url` / `sha256` in `Formula/gittan.rb` (new sdist).
3. Re-run `brew install --build-from-source` and `brew test` locally.
4. Commit + push the tap repo; consider a **tag** or changelog line in the tap README.

---

## Related

- PyPI project: https://pypi.org/project/timelog-extract/  
- Repository: https://github.com/mbjorke/timelog-extract  
