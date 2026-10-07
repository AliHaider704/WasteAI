# File: content/tools/check_tokens.py
"""Token checker (M14a, D-020).

1. Every var(--x) used in frontend/css/ is defined in tokens.css (exit 1 otherwise).
2. Text token pairs meet 4.5:1; chip fill against its text 4.5:1; chip boundary
   (fill or the 1px --color-border-strong border, whichever is stronger) meets 3:1
   against the surface (WCAG 1.4.3 / 1.4.11). Checked for light and dark.
Run from the repo root: python3 content/tools/check_tokens.py
"""
import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "frontend" / "css"
BINS = ["blue", "green", "yellow", "red", "black", "brown", "grey", "special"]
TEXT_PAIRS = [
    ("text", "bg"), ("text", "surface"), ("text-muted", "bg"), ("text-muted", "surface"),
    ("on-accent", "accent"), ("on-accent", "accent-hover"), ("accent", "surface"),
    ("accent", "bg"), ("warning-text", "warning-bg"), ("danger-text", "danger-bg"),
]


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def decls(block):
    return dict(re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{6})\b", block))


def themes(css):
    """Return (light, dark) dicts of color tokens."""
    i = css.index("@media (prefers-color-scheme: dark)")
    j = css.index(':root[data-theme="dark"]')
    light = decls(css[:i])
    dark = decls(css[j:css.index("/* Theme-independent", j)])
    return light, dark


def main():
    tokens = (CSS / "tokens.css").read_text(encoding="utf-8")
    defined = set(re.findall(r"(--[\w-]+)\s*:", tokens))
    bad = []
    for f in sorted(CSS.glob("*.css")):
        for m in re.finditer(r"var\((--[\w-]+)", f.read_text(encoding="utf-8")):
            if m.group(1) not in defined:
                bad.append((f.name, m.group(1)))
    for f, n in sorted(set(bad)):
        print(f"UNDEFINED  {f}: {n}")

    light, dark = themes(tokens)
    fails = 0
    print(f"{'theme':5} {'pair':34} {'ratio':>6}  need  result")
    for name, t in (("light", light), ("dark", dark)):
        rows = []
        for fg, bg in TEXT_PAIRS:
            rows.append((f"--color-{fg} / {bg}", t[f"--color-{fg}"], t[f"--color-{bg}"], 4.5))
        for b in BINS:
            f, g = t[f"--bin-{b}-fg"], t[f"--bin-{b}-bg"]
            rows.append((f"chip text {b}", f, g, 4.5))
            edge = max((g, t["--color-border-strong"]), key=lambda c: ratio(c, t["--color-surface"]))
            rows.append((f"chip edge {b}", edge, t["--color-surface"], 3.0))
        rows.append(("focus / bg", t["--color-focus"], t["--color-bg"], 3.0))
        rows.append(("border-strong / surface", t["--color-border-strong"], t["--color-surface"], 3.0))
        for label, a, b, need in rows:
            r = ratio(a, b)
            ok = r >= need
            fails += not ok
            print(f"{name:5} {label:34} {r:6.2f}  {need:<4}  {'PASS' if ok else 'FAIL'}")

    fonts = CSS.parent / "assets" / "fonts"
    for fam in sorted(p for p in fonts.iterdir() if p.is_dir()):
        lic = fam / "OFL.txt"
        if not lic.exists() or "Open Font License" not in lic.read_text(encoding="utf-8", errors="ignore"):
            print(f"LICENCE    {fam.name}: OFL.txt missing or not OFL")
            fails += 1
    if bad or fails:
        print(f"FAILED: {len(set(bad))} undefined token(s), {fails} failing check(s)")
        return 1
    print("OK: all tokens defined, all contrast pairs pass, fonts licensed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
