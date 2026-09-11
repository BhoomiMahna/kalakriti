import { useState } from "react";

// Speaker button: reads `text` aloud. The voice is chosen from the SCRIPT of the
// text itself (Gurmukhi→Punjabi, Devanagari→Hindi, Latin→English) so English
// marketplace content is never spoken with a Punjabi/Hindi voice, and vice-versa.
// Prefers Sarvam TTS (/api/tts); falls back to the browser speech synthesizer.
const BCP = { hi: "hi-IN", pa: "pa-IN", en: "en-IN" };

function detectLang(text) {
  if (/[਀-੿]/.test(text)) return "pa"; // Gurmukhi
  if (/[ऀ-ॿ]/.test(text)) return "hi"; // Devanagari
  return "en";
}

export default function Speak({ text, className = "" }) {
  const [busy, setBusy] = useState(false);

  async function play() {
    if (!text || busy) return;
    const lang = detectLang(text);
    setBusy(true);
    try {
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language: lang }),
      });
      if (res.ok) {
        const { audio } = await res.json();
        const el = new Audio(`data:audio/wav;base64,${audio}`);
        el.onended = () => setBusy(false);
        el.onerror = () => fallback(lang);
        await el.play();
        return;
      }
      fallback(lang);
    } catch {
      fallback(lang);
    }
  }

  function fallback(lang) {
    // The browser's Hindi/Punjabi voices are poor or absent, so for Indic
    // languages we rely on Sarvam only — a bad robotic voice is worse than none.
    if (lang === "pa" || lang === "hi") {
      setBusy(false);
      return;
    }
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = BCP[lang] || "en-IN";
      // Prefer a voice that matches the language if the browser has one.
      const voices = window.speechSynthesis.getVoices() || [];
      const match = voices.find((v) => v.lang && v.lang.toLowerCase().startsWith(lang));
      if (match) u.voice = match;
      u.onend = () => setBusy(false);
      u.onerror = () => setBusy(false);
      window.speechSynthesis.speak(u);
    } catch {
      setBusy(false);
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
