# Gittan brand assets

**Canonical masters** (edit these, then run the script):


| File                    | Role                                             |
| ----------------------- | ------------------------------------------------ |
| `gittan-brand-mark.png` | Wide master (mascot + terminal frame + pixel **GITTAN**; moving toward bumblebee + berries — see `identity.md`). |
| `gittan-og-card.png`    | Landscape Open Graph card.                       |


**Generated at repo root** (do not hand-edit — regenerate):


| Output                   | Role                                                                                                                                               |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `favicon.ico`            | Browser tab icon                                                                                                                                   |
| `gittan-readme-icon.png` | README hero (128×128)                                                                                                                              |
| `**gittan-logo.png`**    | **Site + nav logo** (default **768×768**, square center-crop, nearest-neighbor = **taggig** text) — used by `**gittan.html`** and **GitHub Pages** |
| `og-image.png`           | Social preview card (copy of `gittan-og-card.png`)                                                                                                 |


```bash
./scripts/build_brand_assets.sh
```

Optional: `BRAND_LOGO_PX=512` for a smaller `gittan-logo.png`; `BRAND_RESIZE_FILTER=lanczos` for smoother (less pixel-crisp) scaling.

**Archive:** `[archive/](archive/)` — backup copies of older masters (e.g. rabbit-v2 era).

**Drafts:** `[drafts/](drafts/)` — experiments before promoting over the canonical PNGs.

**Intent:** `[identity.md](identity.md)`.

**Tooling:** ImageMagick (`magick`) preferred for multi-size `.ico` and pipeline; Pillow fallback squares and uses `NEAREST`.

**GitHub Social preview** (1280×640 Settings upload): optional; see `repository-open-graph-template.png` at repo root.