# File: content/tools/check_content.py
"""Validate guidance content and UI strings. Run from anywhere: python3 content/tools/check_content.py

Checks: category ID coverage vs contract/categories.json, ar/en parity, 3-5 steps, hazard warnings,
frontend/i18n ar/en key parity, i18n keys used in the frontend exist, and the 500-line file limit.
index.html shell rules (translatable attributes, no hardcoded text),
UI leak scan (raw keys, {n}, merge markers) lives in check_ui_leaks.py.
Exit code 1 if any error is found.
"""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LANGS = ("ar", "en")
HAZARD_IDS = {"battery", "hazardous_chemical", "medical"}
HAZARD_PREFIX = "ewaste_"
MAX_LINES = 500
ARABIC = re.compile(r"[\u0600-\u06FF]")
KEY_RE = re.compile(
    r'["\']((?:why|app|nav|ctl|home|result|browse|group|bin|capture|camera|upload|loading|error|feedback|agreement|source|consent)'
    r"\.[A-Za-z0-9_.\-]+)[\"']"
)
errors = []


def err(message):
    errors.append(message)


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        err(f"{path.relative_to(ROOT)}: cannot read ({exc})")
        return None


def is_hazard(cat_id):
    return cat_id in HAZARD_IDS or cat_id.startswith(HAZARD_PREFIX)


def contract_ids():
    data = load_json(ROOT / "contract" / "categories.json")
    items = data.get("categories") if isinstance(data, dict) else data
    if not isinstance(items, list):
        err("contract/categories.json: expected a list of categories")
        return []
    return [c["id"] for c in items if isinstance(c, dict) and "id" in c]


def check_guidance(lang, ids):
    path = ROOT / "content" / f"guidance.{lang}.json"
    data = load_json(path)
    cats = data.get("categories") if isinstance(data, dict) else None
    if not isinstance(cats, dict):
        err(f"{path.name}: missing 'categories' object")
        return {}
    for cat_id in ids:
        entry = cats.get(cat_id)
        if not isinstance(entry, dict):
            err(f"{lang}: missing category '{cat_id}'")
            continue
        for field in ("name", "summary"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                err(f"{lang}/{cat_id}: '{field}' must be a non-empty string")
        steps = entry.get("steps")
        if not isinstance(steps, list) or not 3 <= len(steps) <= 5:
            err(f"{lang}/{cat_id}: needs 3-5 steps (found {len(steps) if isinstance(steps, list) else 'none'})")
        elif any(not isinstance(s, str) or not s.strip() for s in steps):
            err(f"{lang}/{cat_id}: empty step text")
        warnings = entry.get("warnings")
        if not isinstance(warnings, list) or any(not isinstance(w, str) or not w.strip() for w in warnings):
            err(f"{lang}/{cat_id}: 'warnings' must be a list of non-empty strings")
        elif is_hazard(cat_id) and not warnings:
            err(f"{lang}/{cat_id}: hazard category needs at least one warning")
        name = entry.get("name", "")
        if lang == "ar" and not ARABIC.search(name):
            err(f"ar/{cat_id}: name has no Arabic letters")
        if lang == "en" and ARABIC.search(name):
            err(f"en/{cat_id}: name contains Arabic letters")
    for extra in sorted(set(cats) - set(ids)):
        err(f"{lang}: unknown category '{extra}' (not in contract)")
    return cats


def check_parity(ids, ar, en):
    for cat_id in ids:
        a, e = ar.get(cat_id), en.get(cat_id)
        if not isinstance(a, dict) or not isinstance(e, dict):
            continue
        for field in ("steps", "warnings"):
            if len(a.get(field, [])) != len(e.get(field, [])):
                err(f"parity {cat_id}: '{field}' count differs (ar {len(a.get(field, []))}, en {len(e.get(field, []))})")


def check_i18n():
    dicts = {}
    for lang in LANGS:
        data = load_json(ROOT / "frontend" / "i18n" / f"{lang}.json")
        if isinstance(data, dict):
            dicts[lang] = {k: v for k, v in data.items() if not k.startswith("_")}
    if len(dicts) != 2:
        return
    ar, en = dicts["ar"], dicts["en"]
    for key in sorted(set(en) - set(ar)):
        err(f"i18n: '{key}' missing in ar.json")
    for key in sorted(set(ar) - set(en)):
        err(f"i18n: '{key}' missing in en.json")
    for lang, d in dicts.items():
        for key, value in d.items():
            if not isinstance(value, str) or not value.strip():
                err(f"i18n/{lang}: '{key}' is empty")
    for key in set(ar) & set(en):
        if set(re.findall(r"\{\w+\}", str(ar[key]))) != set(re.findall(r"\{\w+\}", str(en[key]))):
            err(f"i18n: placeholder mismatch in '{key}'")
    used = set()
    files = [ROOT / "frontend" / "index.html", *sorted((ROOT / "frontend" / "js").glob("*.js"))]
    for path in files:
        if path.exists():
            used |= {k for k in KEY_RE.findall(path.read_text(encoding="utf-8")) if "${" not in k}
    for key in sorted(used - set(en)):
        err(f"i18n: key '{key}' is used in the frontend but missing from en.json")


BDI = re.compile(r'<bdi dir="ltr">([^<]*)</bdi>')
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")


def strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key, value in node.items():
            if not key.startswith("_"):
                yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)


def check_text_rules():
    allow = load_json(ROOT / "content" / "tools" / "allowlist.json") or {}
    allowed = set(allow.get("tokens", [])) | set(allow.get("brands", []))
    files = [f"frontend/i18n/{lang}.json" for lang in LANGS] + [f"content/guidance.{lang}.json" for lang in LANGS]
    files += [f"frontend/i18n/labels.{lang}.json" for lang in LANGS]
    files += [f"frontend/i18n/bins.{lang}.json" for lang in LANGS]
    files += [f"frontend/i18n/features/{p.name}" for p in sorted((ROOT / "frontend" / "i18n" / "features").glob("*.json"))]
    pairs = []
    for rel in files:
        data = load_json(ROOT / rel)
        lang = "ar" if ".ar." in rel or rel.endswith("/ar.json") else "en"
        pairs += [(rel, lang, x) for x in strings(data)]
    for path in sorted((ROOT / "frontend" / "data").glob("*.json")):
        if path.name == "features.json":
            continue
        rel = path.relative_to(ROOT).as_posix()
        for e in (load_json(path) or {}).get("entries", []):
            pairs += [(rel, lg, x) for lg in LANGS for x in strings(e.get(lg))]
    for rel, lang, text in pairs:
        if "frontend/data/" in rel or "i18n/features/" in rel:
            bare = re.sub(r"\b(" + "|".join(map(re.escape, allowed or ["-"])) + r")\b", "", text)
            if re.search(r"[A-Za-z]{3,}", bare) and bare == bare.upper() and lang == "en":
                err(f"{rel}: all-caps text: {text[:50]!r}")
            if text.rstrip().endswith(("\u2192", "\u2190", "\u2197", "\u279c", "->", ">>", "\u00bb")):
                err(f"{rel}: text ends with an arrow: {text[:50]!r}")
        if "..." in text or "\u2014" in text or EMOJI.search(text):
            err(f"{rel}: no '...', em dash or emoji allowed: {text[:50]!r}")
        if lang == "en" and ARABIC.search(text):
            err(f"{rel}: Arabic letters in an English file: {text[:50]!r}")
        if lang == "ar":
            for token in BDI.findall(text):
                if token not in allowed:
                    err(f"{rel}: '{token}' is not in content/tools/allowlist.json")
            rest = re.sub(r"\{\w+\}", "", BDI.sub("", text))
            if re.search(r"[A-Za-z]", rest):
                err(f"{rel}: Latin letters outside <bdi> allow-list: {text[:50]!r}")


def rule_labels():
    found = set()
    for path in sorted((ROOT / "server" / "data" / "label_rules").glob("*.json")):
        data = load_json(path)
        if isinstance(data, dict):
            found |= set(data.get("labels", {}))
    stop = load_json(ROOT / "server" / "data" / "azure_stoplist.json") or {}
    return found | set(stop.get("stop", []))


ATTRS = ("aria-label", "placeholder", "title", "alt")
SKIP_TEXT = {"script", "style", "noscript", "title"}


class ShellScan(HTMLParser):
    """Collects shell problems: untranslated attributes and text nodes outside data-i18n elements."""

    def __init__(self):
        super().__init__()
        self.problems = []
        self.stack = []  # (tag, translated?)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        mapped = {p.split(":")[0].strip() for p in a.get("data-i18n-attr", "").split(";") if ":" in p}
        for name in ATTRS:
            if name in a and name not in mapped:
                self.problems.append(f"index.html line {self.getpos()[0]}: <{tag} {name}> must use data-i18n-attr")
        if tag in ("meta", "link", "br", "img", "input", "use", "source"):
            return
        parent = self.stack[-1][1] if self.stack else False
        self.stack.append((tag, parent or "data-i18n" in a or tag in SKIP_TEXT))

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def handle_data(self, data):
        if data.strip() and not (self.stack and self.stack[-1][1]):
            self.problems.append(f"index.html line {self.getpos()[0]}: hardcoded text {data.strip()[:40]!r}")


def check_index_shell():
    path = ROOT / "frontend" / "index.html"
    html = path.read_text(encoding="utf-8")
    scan = ShellScan()
    scan.feed(re.sub(r"<!--.*?-->|<!DOCTYPE[^>]*>", "", html, flags=re.S))
    for message in scan.problems:
        err(message)
    root = re.search(r"<html[^>]*>", html)
    if not root or "data-i18n-pending" not in root.group(0) or "lang=" not in root.group(0) or "dir=" not in root.group(0):
        err("index.html: <html> needs lang, dir and data-i18n-pending")
    if not re.search(r"<noscript>[^<]*</noscript>|<noscript>.*?lang=\"ar\".*?lang=\"en\"", html, re.S):
        err("index.html: <noscript> needs a message in Arabic and in English")


def check_labels():
    dicts = {}
    for lang in LANGS:
        data = load_json(ROOT / "frontend" / "i18n" / f"labels.{lang}.json")
        if isinstance(data, dict):
            dicts[lang] = {k: v for k, v in data.items() if not k.startswith("_")}
    if len(dicts) != 2:
        return
    for lang, d in dicts.items():
        for key in sorted(rule_labels() - set(d)):
            err(f"labels.{lang}: no translation for rule label '{key}'")
        for key, value in d.items():
            if not isinstance(value, str) or not value.strip():
                err(f"labels.{lang}: '{key}' is empty")
            elif lang == "ar" and not ARABIC.search(value):
                err(f"labels.ar: '{key}' has no Arabic letters")
    if set(dicts["ar"]) != set(dicts["en"]):
        err("labels: ar/en keys differ")


def check_source_names():
    data = load_json(ROOT / "frontend" / "i18n" / "source_names.json")
    if not isinstance(data, dict):
        err("source_names.json: missing or invalid")
        return
    allow = load_json(ROOT / "content" / "tools" / "allowlist.json") or {}
    brands = set(allow.get("brands", []))
    names = {k: v for k, v in data.items() if not k.startswith("_")}
    for key, value in names.items():
        if not isinstance(value, str) or not value.strip() or ARABIC.search(value):
            err(f"source_names: '{key}' must be a Latin name")
        elif value not in brands:
            err(f"source_names: '{value}' is not in allowlist.json brands")
        for lang in LANGS:
            d = load_json(ROOT / "frontend" / "i18n" / f"{lang}.json") or {}
            if f"source.{key}" not in d:
                err(f"{lang}.json: missing key source.{key}")
    for extra in sorted(brands - set(names.values())):
        err(f"allowlist brand '{extra}' is not used in source_names.json")


BIN_LISTS = ("accepts", "rejects", "prepare")
BIN_TEXTS = ("tagline", "definition", "why")


def check_bins():
    """Bin details (Home dialog): every bin of the contract, same shape in ar and en, Arabic text is Arabic."""
    cats = load_json(ROOT / "contract" / "categories.json")
    cats = cats.get("categories", []) if isinstance(cats, dict) else cats
    want = {c["bin"] for c in cats}
    data = {}
    for lang in LANGS:
        doc = load_json(ROOT / "frontend" / "i18n" / f"bins.{lang}.json")
        data[lang] = (doc or {}).get("bins")
        if not isinstance(data[lang], dict):
            err(f"bins.{lang}.json: missing or invalid")
            return
        if set(data[lang]) != want:
            err(f"bins.{lang}.json: bins {sorted(data[lang])} differ from the contract {sorted(want)}")
    for bin_id in sorted(want):
        a, e = data["ar"].get(bin_id, {}), data["en"].get(bin_id, {})
        for key in BIN_TEXTS:
            if not a.get(key) or not e.get(key):
                err(f"bins.{bin_id}.{key}: empty in ar or en")
            elif not ARABIC.search(a[key]):
                err(f"bins.ar.{bin_id}.{key}: has no Arabic letters")
        for key in BIN_LISTS:
            if not a.get(key) or len(a[key]) != len(e.get(key) or []):
                err(f"bins.{bin_id}.{key}: ar and en lists differ in length")
        for key in ("bin." + bin_id,):
            for lang in LANGS:
                if key not in (load_json(ROOT / "frontend" / "i18n" / f"{lang}.json") or {}):
                    err(f"{lang}.json: missing key {key}")


def check_line_limits():
    paths = [ROOT / "content" / f"guidance.{lang}.json" for lang in LANGS]
    paths += [ROOT / "frontend" / "i18n" / f"{lang}.json" for lang in LANGS] + [Path(__file__)]
    for path in paths:
        if path.exists() and len(path.read_text(encoding="utf-8").splitlines()) > MAX_LINES:
            err(f"{path.name}: more than {MAX_LINES} lines (split by group and log a DECISIONS entry)")


def main():
    ids = contract_ids()
    ar = check_guidance("ar", ids)
    en = check_guidance("en", ids)
    check_parity(ids, ar, en)
    check_i18n()
    check_text_rules()
    check_index_shell()
    check_labels()
    check_source_names()
    check_bins()
    check_line_limits()
    if errors:
        print(f"FAILED: {len(errors)} problem(s)")
        for message in errors:
            print(f" - {message}")
        return 1
    print(f"OK: {len(ids)} categories x {len(LANGS)} languages, i18n keys in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
