// File: frontend/js/speech.js
// Shared speech helper (audio.js and features/read-aloud.js). No voice is ever bundled: it uses the device's own
// speechSynthesis. Arabic voices are often late to load, listed as "ar_SA" (Android) or absent, so this file
// waits for the list, matches by language prefix, and lets callers fall back to the engine default.

const LETTERS = {
  A: "إيه", B: "بي", C: "سي", D: "دي", E: "إي", F: "إف", G: "جي", H: "إتش", I: "آي", J: "جيه", K: "كيه", L: "إل", M: "إم",
  N: "إن", O: "أو", P: "بي", Q: "كيو", R: "آر", S: "إس", T: "تي", U: "يو", V: "في", W: "دبليو", X: "إكس", Y: "واي", Z: "زد",
};

export const supported = () =>
  typeof window !== "undefined" && "speechSynthesis" in window && typeof SpeechSynthesisUtterance !== "undefined";

const langCode = (lang) => String(lang || "en").replace("_", "-").slice(0, 2).toLowerCase();

/** Resolves with the voice list once the browser has filled it (or after `ms`, possibly empty). */
export function voicesReady(ms = 1500) {
  return new Promise((resolve) => {
    if (!supported()) return resolve([]);
    const syn = window.speechSynthesis;
    const have = () => syn.getVoices() || [];
    if (have().length) return resolve(have());
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      syn.removeEventListener && syn.removeEventListener("voiceschanged", finish);
      resolve(have());
    };
    syn.addEventListener && syn.addEventListener("voiceschanged", finish);
    setTimeout(finish, ms);
  });
}

/** Best voice for a language: default first, then on-device (works offline), then the most common region. */
export function pickVoice(lang) {
  if (!supported()) return null;
  const code = langCode(lang);
  const rank = (v) =>
    (v.default ? 0 : 4) + (v.localService ? 0 : 2) + (/^(ar|en)[-_](sa|us)$/i.test(String(v.lang)) ? 0 : 1);
  const matches = (window.speechSynthesis.getVoices() || [])
    .filter((v) => String(v.lang).replace("_", "-").toLowerCase().startsWith(code))
    .sort((a, b) => rank(a) - rank(b));
  return matches[0] || null;
}

/** Text a speech engine reads well. Arabic: spell all-caps Latin codes (PET, HDPE) letter by letter. */
export function speakable(text, lang) {
  let s = String(text || "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  if (langCode(lang) === "ar") {
    s = s.replace(/\b[A-Z]{2,6}\b/g, (w) => [...w].map((c) => LETTERS[c] || c).join(" "));
    s = s.replace(/\(\s*(\d)\s*\)/g, "، $1");
  }
  return s;
}

export function cancel() {
  try { if (supported()) window.speechSynthesis.cancel(); } catch (err) { /* ignore */ }
}

/**
 * Speaks `parts` one utterance each (long single utterances are cut off by some browsers).
 * Without a matching voice it still tries the engine default for the language, unless `needVoice` is set.
 * Resolves with "done", "no-voice" or "error". Calls onStart once when audio really begins.
 */
export async function speakParts(parts, { lang, volume = 0.85, rate, needVoice = false, onStart } = {}) {
  if (!supported()) return "error";
  const ar = langCode(lang) === "ar";
  await voicesReady();
  const voice = pickVoice(lang);
  if (!voice && needVoice) return "no-voice";
  const list = parts.map((p) => speakable(p, lang)).filter(Boolean);
  if (!list.length) return "done";
  const syn = window.speechSynthesis;
  syn.cancel();
  await new Promise((r) => setTimeout(r, 60)); // Chrome drops a speak() issued right after cancel()
  return new Promise((resolve) => {
    let started = false;
    let finished = false;
    const end = (result) => {
      if (finished) return;
      finished = true;
      clearTimeout(watchdog);
      resolve(result);
    };
    // Engines with no usable voice often stay silent without any event: give up after 4 s.
    const watchdog = setTimeout(() => { if (!started) { cancel(); end("no-voice"); } }, 4000);
    list.forEach((text, i) => {
      const u = new SpeechSynthesisUtterance(text);
      u.lang = voice ? voice.lang : ar ? "ar-SA" : String(lang || "en");
      if (voice) u.voice = voice;
      u.volume = volume;
      u.rate = rate || (ar ? 0.9 : 0.95);
      u.onstart = () => { if (!started) { started = true; if (onStart) onStart(); } };
      if (i === list.length - 1) u.onend = () => end(started ? "done" : "no-voice");
      u.onerror = (e) => {
        if (e && (e.error === "canceled" || e.error === "interrupted")) return end("done");
        end(e && /language|voice|unavailable/.test(e.error || "") ? "no-voice" : "error");
      };
      try { syn.speak(u); } catch (err) { end("error"); }
    });
  });
}
