<!-- File: frontend/design/DESIGN.md -->
# Design: D3 kraft and ink (D-020)

Status: written from the owner-approved direction (Q1). Owner approves this file.

Read: camera-first utility app for households and students, recycled-paper style, stamped bin label. Dials ENERGY 2 / RHYTHM 2 / MOTION 2.

## Palette (values live in `css/tokens.css`; `content/tools/check_tokens.py` verifies contrast)

| Token | Light | Dark | Reason |
|---|---|---|---|
| bg | #E9E1D3 | #1B1916 | Flat kraft; no texture, no gradient |
| surface | #F6F1E6 | #26231F | Cards separate from bg by color and 1 px border, not shadow |
| text | #25221D | #EDE6D8 | 12:1+ on bg |
| accent (ink blue) | #23405E | #8FB4DC | One accent; no terracotta anywhere |
| focus | #1E4FA0 | #9DBDF0 | Distinct from accent, 3:1+ on bg |
| special bin | #8A3B12 | #E39A6B | Burnt brown-orange, bin color only (F-21), never a UI accent |

## Type

| Role | Arabic | Latin | Weights |
|---|---|---|---|
| Body, UI, steps | IBM Plex Sans Arabic | IBM Plex Sans | 400, 500, 600 |
| Category name only | Noto Naskh Arabic | Newsreader | 500, 600 |

Reason: the Plex pair shares x-heights, so `<bdi>` Latin tokens do not jump inside Arabic text. Serif appears once per screen as the focal word. Files: `assets/fonts/<family>/`, subset to Arabic or Latin, `OFL.txt` beside each. Fallbacks use `size-adjust` to limit layout shift.

## Shape and motif

- Radius 4 px (chips, inputs), 8 px (cards), 999 px only on the three header toggles. No card shadow.
- Motif: the stamped bin label, a bordered chip in the bin color rotated about -2 degrees (applied in M15: every `.bin` chip, result card, Browse rows, one decorative row on Home).
- Chips carry `1px solid var(--color-border-strong)` so yellow and black chips stay visible in both themes (F-22).

## Motion

Opacity and transform only, inside `prefers-reduced-motion: no-preference` (M14b).

## Layout (M15)

- Result: stamped bin chip, then the serif category name as the one focal word, then confidence word, numbered steps (a real sequence), warnings, "Why?", feedback. Hazard warnings stay visible at any confidence.
- Home: Scan is the large focal action, Upload secondary, Browse a quiet link; the only decoration is one row of stamped bin chips. No card grid.
- Motion: chip stamp-down 160 ms once per result, Browse rows rise 4 px, confidence word cross-fades 150 ms.

## Swap-the-logo test

Swap the product name and the page still reads as bin signage: a bordered, bin-colored stamp tilted -2 degrees above one serif word, repeated on result, Browse and Home.
