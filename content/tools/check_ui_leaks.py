# File: content/tools/check_ui_leaks.py
"""Static scan for text that must never reach the UI. Run: python3 content/tools/check_ui_leaks.py

Checks (frontend/**):
1. every data-i18n / data-i18n-attr key and every t("...") / tHtml("...") key exists in en.json and ar.json
   (template keys like t(`bin.${x}`) need at least one dictionary key with that prefix);
2. every key-like string literal in js/*.js (known namespace, e.g. "browse.count") outside t() calls must be
   a real dictionary key (keys kept in maps and passed to t() later are fine; typos would leak raw ids);
3. no literal {n} outside the i18n dictionaries (template ${n} and .replace("{n}", ...) are fine);
4. no git merge markers in frontend/ or content/.
Exit code 1 on any hit.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend"
TEXT_EXT = {".js", ".html", ".css", ".json", ".md", ".py", ".svg"}
T_CALL = re.compile(r"""\b(?:t|tHtml)\(\s*(["'`])([^"'`]+)\1""")
DATA_I18N = re.compile(r'data-i18n="([^"]+)"')
DATA_ATTR = re.compile(r'data-i18n-attr="([^"]+)"')
STRING = re.compile(r"""(["'])([a-z_.\-]+\.[a-z_.\-]+)\1""")
BRACE_N = re.compile(r"(?<!\$)\{n\}")
MARKER = re.compile(r"^(<{7}|>{7}|={7})(\s|$)")
errors = []


def err(msg):
    errors.append(msg)


def rel(p):
    return str(p.relative_to(ROOT))


def load_dict(lang):
    data = json.loads((FE / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
    return {k for k in data if not k.startswith("_")}


def code_lines(text):
    for no, line in enumerate(text.splitlines(), 1):
        if not line.strip().startswith(("//", "/*", "*", "<!--")):
            yield no, line


def check_key(key, where, dicts):
    if "${" in key:
        prefix = key.split("${")[0]
        for lang, keys in dicts.items():
            if not any(k.startswith(prefix) for k in keys):
                err(f"{where}: no {lang} key with prefix '{prefix}'")
    else:
        for lang, keys in dicts.items():
            if key not in keys:
                err(f"{where}: key '{key}' missing in {lang}.json")


def main():
    dicts = {lang: load_dict(lang) for lang in ("ar", "en")}
    for lang in dicts:
        for ns in sorted((FE / "i18n" / "features").glob(f"*.{lang}.json")):
            dicts[lang] |= {k for k in json.loads(ns.read_text(encoding="utf-8")) if not k.startswith("_")}
    namespaces = {k.split(".")[0] for k in dicts["en"] if "." in k}
    for path in sorted(list(FE.rglob("*")) + list((ROOT / "content").rglob("*"))):
        if not path.is_file() or path.suffix not in TEXT_EXT or "fonts" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for no, line in enumerate(text.splitlines(), 1):
            if MARKER.match(line):
                err(f"{rel(path)}:{no}: merge marker")
        if path.suffix == ".py" or "i18n" in path.parts and path.suffix == ".json":
            continue
        if path.name == "leak_test.html":
            continue
        if path.suffix in {".js", ".html"}:
            for no, line in code_lines(text):
                if BRACE_N.search(line) and '.replace("{n}"' not in line:
                    err(f"{rel(path)}:{no}: literal {{n}}")
        if path.suffix == ".html":
            for key in DATA_I18N.findall(text):
                check_key(key, rel(path), dicts)
            for spec in DATA_ATTR.findall(text):
                for part in spec.split(";"):
                    if ":" in part:
                        check_key(part.split(":", 1)[1].strip(), rel(path), dicts)
        if path.suffix == ".js":
            for no, line in code_lines(text):
                calls = T_CALL.findall(line)
                for _, key in calls:
                    check_key(key, f"{rel(path)}:{no}", dicts)
                stripped = T_CALL.sub("", line)
                if "i18n" in stripped and "dataset" in stripped:
                    continue
                for _, lit in STRING.findall(stripped):
                    if lit.split(".")[0] in namespaces and lit not in dicts["en"]:
                        err(f"{rel(path)}:{no}: key-like string '{lit}' outside t() is not a dictionary key")
    if errors:
        print("UI LEAK CHECK FAILED")
        print("\n".join(errors))
        sys.exit(1)
    print("OK: no UI leak patterns found")


main()
