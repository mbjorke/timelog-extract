# Homebrew packaging (tap) — staging files

**Authoritative instructions:** [`docs/runbooks/homebrew-tap.md`](../../docs/runbooks/homebrew-tap.md).

This folder holds **notes and checksum snapshots** only. The real tap lives in a **separate** GitHub repo (e.g. `homebrew-gittan`), not in this application repository.

## PyPI sdist snapshot (timelog-extract 0.2.11)

Used when writing [`docs/runbooks/homebrew-tap.md`](../../docs/runbooks/homebrew-tap.md); **update on each release**.

| Field | Value |
|--------|--------|
| **sdist URL** | `https://files.pythonhosted.org/packages/48/1e/2c35e6c5ac539251f42f9aedd594ac61ebe094b96904aeec54c133d5cd02/timelog_extract-0.2.11.tar.gz` |
| **sha256** | `2b9dbe01b1e074f608541eb6e2c5ddec9ad83600a76ad28860ccda3eebed6ca2` |

## Do not commit a full `gittan.rb` here without `brew audit`

A correct formula includes **all** `resource` blocks for transitive Python deps. Generate it with:

`brew create --python --set-name gittan "<sdist url>"`

on a machine with Homebrew **core** tapped, then copy the result into your **`homebrew-gittan`** repo.
