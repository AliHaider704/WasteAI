# File: content/tools/m51_tags.py
"""M51: Arabic and English names for the Azure tags in the A38 hand-off file.

  python3 content/tools/m51_tags.py --apply   # add missing tags to labels.en.json and labels.ar.json
  python3 content/tools/m51_tags.py           # check: every hand-off tag exists in both dictionaries

Existing entries are never changed. Arabic strings are unreviewed (M25 list).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
I18N = ROOT / "frontend" / "i18n"
HANDOFF = ROOT / "docs" / "phases" / "accuracy" / "handoff" / "azure_tags_for_translation.json"

AR = {
    "general supply": "مستلزمات عامة", "sketch": "رسم تخطيطي", "suede fiber": "ألياف الجلد المدبوغ",
    "toy": "لعبة", "toilet": "مرحاض", "tray": "صينية", "gemstone": "حجر كريم", "window": "نافذة",
    "vehicle": "مركبة", "graphic design": "تصميم جرافيكي", "chocolate": "شوكولاتة",
    "toiletry": "أدوات العناية الشخصية", "brush": "فرشاة", "binding": "تجليد", "comb": "مشط",
    "plane": "طائرة", "eraser": "ممحاة", "clock": "ساعة حائط", "pen": "قلم", "champagne": "شمبانيا",
    "watch": "ساعة يد", "drinkware": "أواني الشرب", "barware": "أدوات البار", "blurry": "غير واضح",
    "pottery": "فخار", "serving dish": "طبق تقديم", "porthole": "كوة سفينة", "reptile": "زاحف",
    "mammal": "ثديي", "emblem": "شعار", "knob": "مقبض", "metalware": "أدوات معدنية",
    "auto part": "قطعة سيارة", "car": "سيارة", "serving tray": "صينية تقديم", "cola": "كولا",
    "copper": "نحاس", "pencil sharpener": "مبراة", "sticker": "ملصق", "poster": "ملصق دعائي",
    "sign": "لافتة", "jack": "رافعة", "lego": "ليغو", "card": "بطاقة", "confectionery": "حلويات",
    "ink": "حبر", "petri dish": "طبق بتري", "creative arts": "فنون إبداعية",
    "cookie cutter": "قاطع بسكويت", "turquoise": "لون فيروزي", "monochrome": "أحادي اللون",
    "door": "باب", "sofa": "أريكة", "case": "علبة", "notebook": "دفتر", "funeral": "جنازة",
    "binder": "ملف حافظ", "line": "خط", "shadow": "ظل", "measuring stick": "مسطرة قياس",
    "natural foods": "أطعمة طبيعية", "bear": "دب", "scissors": "مقص", "soap dish": "حامل صابون",
    "plumbing fixture": "تجهيزات سباكة", "plumbing": "سباكة", "tap": "صنبور",
    "hydrant": "صنبور حريق", "office instrument": "أداة مكتبية", "fountain pen": "قلم حبر",
    "writing implement": "أداة كتابة", "display": "شاشة عرض", "lemon": "ليمون", "citrus": "حمضيات",
    "thumbtack": "دبوس تثبيت", "plug": "قابس", "fish": "سمكة", "perfume": "عطر",
    "stemware": "كؤوس بساق", "champagne stemware": "كؤوس شمبانيا", "bullets": "رصاص",
    "kitchen utensil": "أداة مطبخ", "medical equipment": "معدات طبية", "jewelry": "مجوهرات",
    "hollowware": "أوانٍ مجوفة", "crocodilian reptile": "زاحف من فصيلة التمساح",
    "amphibian": "برمائي", "invertebrate": "لافقاري", "alligator": "تمساح أمريكي", "lock": "قفل",
    "cameras & optics": "كاميرات وبصريات", "projector": "جهاز عرض", "razor": "شفرة حلاقة",
    "brass": "نحاس أصفر", "beetle": "خنفساء", "powder": "مسحوق", "round": "دائري",
    "golf ball": "كرة غولف", "spiral": "حلزوني", "platinum": "بلاتين", "lighter": "ولاعة",
    "reflection": "انعكاس", "gold": "ذهب", "model car": "سيارة نموذجية", "land vehicle": "مركبة برية",
    "armor": "درع", "frisbee": "قرص طائر", "loudspeaker": "مكبر صوت", "teal": "أخضر مزرق",
    "gadget": "جهاز صغير", "maroon": "لون كستنائي", "flag": "علم", "tabloid": "صحيفة شعبية",
    "news": "أخبار", "wind instrument": "آلة نفخ", "horse": "حصان", "cartoon": "رسوم متحركة",
    "board game": "لعبة لوحية", "fog": "ضباب", "ivory": "عاج", "print": "مطبوعة", "shelving": "رفوف",
    "shelf": "رف", "sandwich": "شطيرة", "pillow": "وسادة", "stack": "كومة", "footwear": "أحذية",
    "money": "نقود", "toffee": "توفي", "chocolate bar": "لوح شوكولاتة",
    "post-it note": "ورقة ملاحظات لاصقة", "produce": "خضار وفواكه", "bulb": "مصباح",
    "gelatin": "جيلاتين", "sphere": "كرة", "earphone": "سماعة أذن", "drug": "دواء",
    "earplug": "سدادة أذن", "beaker": "كأس مخبري", "frozen": "مجمد", "milk": "حليب",
    "fire extinguisher": "طفاية حريق", "stain": "بقعة", "chip": "رقاقة", "sled": "مزلقة",
    "stoneware": "خزف حجري", "shotgun shell": "خرطوش بندقية",
    "marine invertebrates": "لافقاريات بحرية", "window blind": "ستارة نافذة", "wool": "صوف",
    "rock": "صخرة", "shaped": "مشكّل", "serveware": "أواني التقديم", "bowl": "وعاء",
    "butterfly": "فراشة", "craft": "حرفة", "coffee": "قهوة", "fictional character": "شخصية خيالية",
    "flash memory": "ذاكرة فلاش",
}
EN = {k: k for k in AR}  # English display name equals the tag


def load(lang: str) -> dict:
    return json.loads((I18N / f"labels.{lang}.json").read_text("utf-8"))


def apply() -> int:
    for lang, add in (("en", EN), ("ar", AR)):
        path = I18N / f"labels.{lang}.json"
        data = load(lang)
        new = {k: v for k, v in add.items() if k not in data}
        data.update(new)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
        print(f"{lang}: +{len(new)} entries, {path.read_text('utf-8').count(chr(10))} lines")
    return 0


def check() -> int:
    bad = 0
    tags = [t["tag"].strip().lower() for t in json.loads(HANDOFF.read_text("utf-8"))["tags"]]
    for lang in ("en", "ar"):
        data = load(lang)
        missing = [t for t in tags if t not in data]
        if missing:
            bad += 1
            print(f"FAIL labels.{lang}.json missing {len(missing)}: {missing[:10]}")
        if lang == "ar":
            latin = [k for k in tags if k in data and re.search("[A-Za-z]", str(data[k]))]
            if latin:
                bad += 1
                print(f"FAIL Latin letters in Arabic entries: {latin[:10]}")
        lines = (I18N / f"labels.{lang}.json").read_text("utf-8").count("\n")
        if lines > 450:
            bad += 1
            print(f"FAIL labels.{lang}.json has {lines} lines (split at 450)")
    print("OK" if not bad else "FAILED", f"({len(tags)} hand-off tags)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(apply() if "--apply" in sys.argv else check())
