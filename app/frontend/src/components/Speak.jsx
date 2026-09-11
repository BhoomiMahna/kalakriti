import { useState } from "react";

// Speaker button: reads `text` aloud. The voice is chosen from the SCRIPT of the
// text itself (Gurmukhi→Punjabi, Devanagari→Hindi, Latin→English) so English
// marketplace content is never spoken with a Punjabi/Hindi voice, and vice-versa.
// Prefers Sarvam TTS (/api/tts, high quality); if that's unavailable it falls
// back to the browser speech synthesizer for EVERY language — an imperfect
// voice is better than silence, and Sarvam is used whenever it's configured.
const BCP = { hi: "hi-IN", pa: "pa-IN", en: "en-IN" };

function detectLang(text) {
  if (/[਀-੿]/.test(text)) return "pa"; // Gurmukhi
  if (/[ऀ-ॿ]/.test(text)) return "hi"; // Devanagari
  return "en";
}

// Browser voices can load asynchronously — resolve once they're available.
function loadVoices() {
  return new Promise((resolve) => {
    const synth = window.speechSynthesis;
    if (!synth) return resolve([]);
    const now = synth.getVoices();
    if (now && now.length) return resolve(now);
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      resolve(synth.getVoices() || []);
    };
    synth.onvoiceschanged = finish;
    setTimeout(finish, 800); // some browsers never fire the event
  });
}

async function browserSpeak(text, lang, onEnd) {
  const synth = window.speechSynthesis;
  if (!synth) return onEnd();
  try {
    const voices = await loadVoices();
    synth.cancel(); // clear anything queued/stuck
    const u = new SpeechSynthesisUtterance(text);
    u.lang = BCP[lang] || "en-IN";
    // Exact language match, else a Hindi voice for Punjabi (nearest), else default.
    const pick =
      voices.find((v) => v.lang && v.lang.toLowerCase().startsWith(lang)) ||
      (lang === "pa" && voices.find((v) => v.lang && v.lang.toLowerCase().startsWith("hi"))) ||
      null;
    if (pick) u.voice = pick;
    u.onend = onEnd;
    u.onerror = onEnd;
    synth.resume(); // some engines start paused
    synth.speak(u);
  } catch {
    onEnd();
  }
}

export default function Speak({ text, className = "" }) {
  const [busy, setBusy] = useState(false);

  async function play() {
    if (!text || busy) return;
    const lang = detectLang(text);
    setBusy(true);
    const done = () => setBusy(false);
    try {
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language: lang }),
      });
      if (res.ok) {
        const { audio } = await res.json();
        const el = new Audio(`data:audio/wav;base64,${audio}`);
        el.onended = done;
        el.onerror = () => browserSpeak(text, lang, done);
        try {
          await el.play();
          return;
        } catch {
          browserSpeak(text, lang, done); // autoplay blocked → browser TTS
          return;
        }
      }
      browserSpeak(text, lang, done); // e.g. 503 when Sarvam key isn't configured
    } catch {
      browserSpeak(text, lang, done);
    }
  }

  return (
    <button
      type="button"
      onClick={play}
      aria-label="Listen"
      className={`inline-flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-brand-600 hover:bg-brand-50 ${
        busy ? "animate-pulse" : ""
      } ${className}`}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
        <path d="M15.5 8.5a5 5 0 0 1 0 7" />
        <path d="M18.5 5.5a9 9 0 0 1 0 13" />
      </svg>
    </button>
  );
}
