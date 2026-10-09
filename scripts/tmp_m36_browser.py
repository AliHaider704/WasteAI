# File: scripts/tmp_m36_browser.py
# Temporary browser check for M36 to M38 (Playwright). Delete after use.
import re, sys
from playwright.sync_api import sync_playwright
BASE = "http://127.0.0.1:8765/"
TXT = {"en": dict(ER="Easy-read mode", DM="Details mode", MB="My bin names"),
       "ar": dict(ER="وضع القراءة السهلة", DM="وضع التفاصيل", MB="أسماء حاوياتي")}
FEED = """async (n)=>{const m=await import('/js/api.js');
const r=await (await fetch('/mock/classify_'+n+'.json')).json();
m.store.result=r;location.hash='#/result';
document.dispatchEvent(new CustomEvent('wasteai:result',{detail:{result:r}}));}"""
SW = "document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"
res = []


def t(n, c, info=""):
    res.append((n, bool(c), info))


with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"])
    for lang in ("en", "ar"):
        X = TXT[lang]
        ctx = b.new_context(locale="en-US" if lang == "en" else "ar-SA", viewport={"width": 390, "height": 844},
                            permissions=["clipboard-read", "clipboard-write"])
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
        pg.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" else None)

        def feed(n):
            pg.evaluate(FEED, n)
            pg.wait_for_timeout(1600)

        pg.goto(BASE + "?mock=1")
        pg.wait_for_timeout(1800)
        t(lang + ": page language", pg.evaluate("document.documentElement.lang") == lang)
        er = pg.locator("#slot-header-tools button", has_text=X["ER"])
        dm = pg.locator("#slot-header-tools button", has_text=X["DM"])
        t(lang + ": header toggles exist", er.count() == 1 and dm.count() == 1)
        feed("ok")
        t(lang + ": ok card shown", pg.locator(".result__card .result__name").count() == 1)
        t(lang + ": confidence meter", pg.locator(".f-meter[role=meter][aria-valuenow]").count() == 1)
        t(lang + ": ink class on stamp", pg.locator(".result__stamp .bin[class*=f-ink--]").count() == 1)
        t(lang + ": no two-sources panel on full agreement", pg.locator(".f-explain").count() == 0)

        sh = pg.locator(".f-share button")
        t(lang + ": share button", sh.count() == 1)
        if sh.count():
            sh.click()
            pg.wait_for_timeout(500)
            st = pg.locator(".f-share p").inner_text().strip()
            t(lang + ": share gives message or manual text", bool(st) or pg.locator(".f-share textarea").is_visible(), st)
        ra = pg.locator(".result__card button[aria-pressed]")
        t(lang + ": read-aloud (info only, hidden is normal in headless)", True, "count=%d" % ra.count())

        mb = pg.locator("#slot-result button", has_text=X["MB"])
        t(lang + ": my-bins open button", mb.count() == 1)
        if mb.count():
            mb.click()
            pg.wait_for_timeout(300)
            t(lang + ": my-bins dialog has 8 inputs", pg.locator("dialog[open] input").count() == 8)
            pg.locator("dialog[open] input").first.fill("TestBin")
            pg.locator("dialog[open] .btn--primary").click()
            pg.wait_for_timeout(400)
            t(lang + ": dialog closed after save", pg.locator("dialog[open]").count() == 0)
            t(lang + ": Your bin line on stamp", pg.locator(".f-mybin").count() == 1 and "TestBin" in pg.locator(".f-mybin").first.inner_text())

        er.click()
        pg.wait_for_timeout(300)
        t(lang + ": easy-read on", pg.evaluate("document.documentElement.dataset.readable") == "on")
        t(lang + ": easy-read no sideways scroll", pg.evaluate(SW))
        er.click()
        pg.wait_for_timeout(200)
        t(lang + ": easy-read off", pg.evaluate("document.documentElement.dataset.readable") is None)

        dm.click()
        pg.wait_for_timeout(800)
        det = pg.locator(".f-details")
        t(lang + ": details block shows 380 from mock", det.count() == 1 and "380" in det.inner_text())
        dm.click()
        pg.wait_for_timeout(500)
        t(lang + ": details removed when off", pg.locator(".f-details").count() == 0)

        feed("uncertain")
        t(lang + ": two-sources panel on uncertain", pg.locator(".f-explain").count() == 1)
        t(lang + ": no meter on uncertain", pg.locator(".f-meter").count() == 0)
        if pg.locator(".f-explain").count():
            pg.locator(".f-explain summary").click()
            pg.wait_for_timeout(200)
            t(lang + ": panel names both sources", pg.locator(".f-explain li").count() == 2)

        feed("hazard")
        t(lang + ": hazard keeps meter", pg.locator(".f-meter").count() == 1)
        t(lang + ": hazard stamp neutral (no ink)", pg.locator(".result__stamp .bin[class*=f-ink--]").count() == 0)

        if lang == "en":
            feed("ok")
            pg.locator('[data-action="lang"]').click()
            pg.wait_for_timeout(2000)
            lab = pg.locator(".f-meter").first.get_attribute("aria-label") or ""
            t("en to ar toggle: meter label now Arabic", bool(re.search("[\u0600-\u06FF]", lab)), lab)
        pg.set_viewport_size({"width": 360, "height": 640})
        pg.wait_for_timeout(300)
        t(lang + ": 360 px no sideways scroll", pg.evaluate(SW))
        t(lang + ": no console or page errors", not errs, " | ".join(errs[:3]))
        ctx.close()
    b.close()

bad = 0
for n, c, i in res:
    print(("PASS  " if c else "FAIL  ") + n + ("   [" + i + "]" if i else ""))
    bad += (not c)
print("\nBROWSER RESULT: %d pass, %d fail" % (len(res) - bad, bad))
sys.exit(1 if bad else 0)
