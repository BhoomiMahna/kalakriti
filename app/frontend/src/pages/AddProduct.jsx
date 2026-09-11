import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";
import { createRecorder } from "../lib/audio.js";
import { useAuth } from "../lib/useAuth.jsx";
import { useI18n } from "../lib/i18n.jsx";
import { Header, Spinner } from "../components/ui.jsx";
import Speak from "../components/Speak.jsx";
import {
  IconCamera,
  IconCheck,
  IconChevronLeft,
  IconMic,
  IconStop,
  IconX,
} from "../components/icons.jsx";

const BackBtn = ({ onClick }) => (
  <button onClick={onClick} className="text-neutral-500">
    <IconChevronLeft />
  </button>
);

export default function AddProduct() {
  const nav = useNavigate();
  const { artisan } = useAuth();
  const { t, lang } = useI18n();
  const [step, setStep] = useState(0);
  const [images, setImages] = useState([]);
  const [transcript, setTranscript] = useState("");

  const titles = [t("add.photosTitle"), t("add.speakTitle"), t("add.processingTitle")];

  function onFiles(e) {
    const files = Array.from(e.target.files || []);
    const added = files.map((f) => ({ file: f, url: URL.createObjectURL(f) }));
    setImages((prev) => [...prev, ...added].slice(0, 6));
  }

  return (
    <>
      <Header
        title={titles[step]}
        back={step < 2 ? <BackBtn onClick={() => (step > 0 ? setStep(step - 1) : nav("/"))} /> : null}
      />
      {step === 0 && (
        <StepPhotos
          t={t}
          images={images}
          onFiles={onFiles}
          removeImage={(i) => setImages((p) => p.filter((_, idx) => idx !== i))}
          next={() => setStep(1)}
        />
      )}
      {step === 1 && (
        <StepSpeak
          t={t}
          lang={lang || artisan?.preferred_language || "en"}
          transcript={transcript}
          setTranscript={setTranscript}
          onConfirm={() => setStep(2)}
        />
      )}
      {step === 2 && (
        <StepProcessing
          t={t}
          payload={{ images, transcript, lang: lang || artisan?.preferred_language || "en" }}
          onDone={(id) => nav(`/product/${id}`, { replace: true })}
        />
      )}
    </>
  );
}

// ─── Step 0: photos ──────────────────────────────────────────────────────────
function StepPhotos({ t, images, onFiles, removeImage, next }) {
  return (
    <>
      <div className="flex-1 space-y-4 p-4">
        <div className="flex items-start gap-2">
          <p className="flex-1 text-neutral-500">{t("add.photosHint")}</p>
          <Speak text={t("add.photosHint")} />
        </div>
        <div className="grid grid-cols-3 gap-3">
          {images.map((im, i) => (
            <div key={i} className="relative aspect-square overflow-hidden rounded-xl bg-neutral-100">
              <img src={im.url} alt="" className="h-full w-full object-cover" />
              <button
                onClick={() => removeImage(i)}
                className="absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-black/60 text-white"
              >
                <IconX size={14} />
              </button>
            </div>
          ))}
          {images.length < 6 && (
            <label className="flex aspect-square cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed border-brand-300 bg-brand-50 text-brand-500">
              <IconCamera />
              <span className="text-xs font-medium">{t("common.addPhoto")}</span>
              <input type="file" accept="image/*" capture="environment" multiple hidden onChange={onFiles} />
            </label>
          )}
        </div>
      </div>
      <div className="sticky bottom-0 border-t border-black/5 bg-white p-4">
        <button className="btn-primary" onClick={next} disabled={images.length === 0}>
          {t("common.continue")}
        </button>
      </div>
    </>
  );
}

// ─── Step 1: speak → transcribe → review ─────────────────────────────────────
function StepSpeak({ t, lang, transcript, setTranscript, onConfirm }) {
  const [mode, setMode] = useState(transcript ? "review" : "idle"); // idle|recording|transcribing|review
  const [seconds, setSeconds] = useState(0);
  const [level, setLevel] = useState(0);
  const [error, setError] = useState("");
  const [debug, setDebug] = useState("");
  const [editing, setEditing] = useState(false);
  const recRef = useRef(null);
  const timer = useRef(null);
  const levelTimer = useRef(null);
  const audioUrl = useRef(null);

  async function startRec() {
    setError("");
    setDebug("");
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.AudioContext && !window.webkitAudioContext) {
      setError(t("add.micInsecure"));
      return;
    }
    try {
      const rec = createRecorder();
      await rec.start();
      recRef.current = rec;
      setMode("recording");
      setSeconds(0);
      setLevel(0);
      timer.current = setInterval(() => setSeconds((s) => s + 1), 1000);
      levelTimer.current = setInterval(() => setLevel(rec.getLevel()), 100);
    } catch (e) {
      if (e && (e.name === "NotAllowedError" || e.name === "SecurityError")) {
        setError(t("add.micDenied"));
      } else if (e && (e.name === "NotFoundError" || e.name === "OverconstrainedError")) {
        setError(t("add.micNoDevice"));
      } else {
        setError(t("add.micUnavailable"));
      }
    }
  }

  async function stopRec() {
    clearInterval(timer.current);
    clearInterval(levelTimer.current);
    setMode("transcribing");
    let result = null;
    try {
      result = await recRef.current.stop();
      if (result?.blob) audioUrl.current = URL.createObjectURL(result.blob);
    } catch {
      /* capture failed — still let them type */
    }
    const wav = result?.blob || null;
    const secs = result ? (result.samples / (result.blob ? 48000 : 1)) : 0; // approx (pre-resample)
    const dbg = (s) =>
      setDebug(`recorded ${(result?.samples ? (result.samples / 48000).toFixed(1) : "0")}s · level ${result?.peak?.toFixed(2) ?? "?"} · ${s}`);

    // If the mic captured (near) silence, say so specifically.
    if (result && result.peak < 0.01) {
      setEditing(true);
      setError(t("add.noSound"));
      dbg("silent");
      setMode("review");
      return;
    }

    // Send to Sarvam STT. Never dead-end: on any failure land on the review card.
    try {
      if (wav) {
        const fd = new FormData();
        fd.append("audio", wav, "voice.wav");
        fd.append("language", lang);
        const res = await api.transcribe(fd);
        setTranscript(res.transcript || "");
        setEditing(!res.transcript);
        if (!res.transcript) {
          // Distinguish "server has no STT configured" from "couldn't understand".
          if (res.stt_available === false) {
            setError(t("add.sttUnavailable"));
            dbg("stt not configured on server");
          } else {
            setError(t("add.couldNotUnderstand"));
            dbg("server ok, empty transcript");
          }
        } else {
          dbg("ok");
        }
      } else {
        setEditing(true);
        setError(t("add.couldNotUnderstand"));
        dbg("no audio blob");
      }
    } catch (e) {
      setEditing(true);
      setError(t("add.couldNotUnderstand"));
      dbg(`server error: ${e.message || e}`.slice(0, 80));
    }
    setMode("review");
  }

  function listen() {
    if (audioUrl.current) new Audio(audioUrl.current).play();
  }

  const prompts = [t("add.prompt1"), t("add.prompt2"), t("add.prompt3")];

  // ── REVIEW CARD ──
  if (mode === "review") {
    return (
      <>
        <div className="flex-1 space-y-4 p-4">
          <div className="card space-y-3">
            <div className="flex items-center justify-between">
              <p className="flex items-center gap-2 font-semibold text-brand-700">
                <IconMic size={18} /> {t("add.weHeard")}
              </p>
              <Speak text={transcript} />
            </div>
            {editing ? (
              <textarea
                autoFocus
                className="input min-h-[120px] text-[15px]"
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
              />
            ) : (
              <p className="whitespace-pre-line rounded-xl bg-neutral-50 p-3 text-[15px] leading-relaxed text-neutral-700">
                {transcript || "…"}
              </p>
            )}
            {error ? (
              <p className="rounded-lg bg-amber-50 p-2 text-xs text-amber-700">{error}</p>
            ) : (
              <p className="text-xs text-neutral-400">{t("add.editHint")}</p>
            )}
            {debug && <p className="font-mono text-[10px] text-neutral-400">{debug}</p>}

            <div className="grid grid-cols-3 gap-2">
              {audioUrl.current && (
                <button onClick={listen} className="btn-chip">
                  <IconMic size={16} /> {t("common.listen")}
                </button>
              )}
              <button onClick={() => setEditing((v) => !v)} className="btn-chip">
                <IconCheck size={16} /> {t("common.edit")}
              </button>
              <button onClick={() => { setEditing(false); startRec(); }} className="btn-chip">
                <IconMic size={16} /> {t("common.recordAgain")}
              </button>
            </div>
          </div>
        </div>
        <div className="sticky bottom-0 border-t border-black/5 bg-white p-4">
          <button className="btn-primary" onClick={onConfirm} disabled={!transcript.trim()}>
            {t("common.confirm")}
          </button>
        </div>
      </>
    );
  }

  // ── RECORD / IDLE ──
  return (
    <>
      <div className="flex-1 space-y-5 p-4">
        <div className="flex items-start gap-2">
          <p className="flex-1 text-neutral-500">{t("add.speakHint")}</p>
          <Speak text={t("add.speakHint")} />
        </div>

        <ul className="space-y-1.5 text-[15px] text-neutral-600">
          {prompts.map((p) => (
            <li key={p} className="flex items-center gap-2">
              <span className="text-brand-400">•</span>
              <span className="flex-1">{p}</span>
              <Speak text={p} />
            </li>
          ))}
        </ul>

        <div className="flex flex-col items-center py-2">
          <button
            onClick={mode === "recording" ? stopRec : startRec}
            disabled={mode === "transcribing"}
            className={`flex h-24 w-24 items-center justify-center rounded-full text-white shadow-lg transition ${
              mode === "recording" ? "animate-pulse bg-rose-500" : "bg-brand-500"
            } disabled:opacity-50`}
          >
            {mode === "transcribing" ? (
              <Spinner className="h-8 w-8 border-white/40 border-t-white" />
            ) : mode === "recording" ? (
              <IconStop size={34} />
            ) : (
              <IconMic size={34} />
            )}
          </button>
          <p className="mt-3 text-center text-sm font-medium text-neutral-500">
            {mode === "transcribing"
              ? t("add.transcribing")
              : mode === "recording"
              ? `${t("add.recording")} · ${seconds}s`
              : t("add.tapToStart")}
          </p>
          {mode === "recording" && (
            <div className="mt-3 h-2.5 w-48 overflow-hidden rounded-full bg-neutral-200">
              <div
                className="h-full rounded-full bg-rose-500 transition-[width] duration-100"
                style={{ width: `${Math.min(100, Math.round(level * 180))}%` }}
              />
            </div>
          )}
        </div>

        {error && <p className="text-center text-sm text-rose-600">{error}</p>}

        <div>
          <label className="label">{t("add.orType")}</label>
          <textarea
            className="input min-h-[90px]"
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            placeholder={t("add.typePh")}
          />
        </div>
      </div>
      <div className="sticky bottom-0 border-t border-black/5 bg-white p-4">
        <button
          className="btn-primary"
          onClick={() => setMode("review")}
          disabled={!transcript.trim()}
        >
          {t("common.continue")}
        </button>
      </div>
    </>
  );
}

// ─── Step 2: processing ──────────────────────────────────────────────────────
const STEP_KEYS = ["understand", "photos", "transcribe", "describe", "story", "price", "assemble"];

function StepProcessing({ t, payload, onDone }) {
  const [steps, setSteps] = useState([]);
  const [error, setError] = useState("");
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      try {
        const fd = new FormData();
        payload.images.forEach((im) => fd.append("images", im.file, im.file.name));
        fd.append("text_hint", payload.transcript || "");
        fd.append("language", payload.lang || "en");
        const product = await api.createProduct(fd);
        const poll = setInterval(async () => {
          try {
            const job = await api.latestJob(product.id);
            if (job?.steps) setSteps(job.steps);
            if (job?.status === "SUCCEEDED") {
              clearInterval(poll);
              setTimeout(() => onDone(product.id), 500);
            } else if (job?.status === "FAILED") {
              clearInterval(poll);
              setError(job.error || "Something went wrong. Your product was saved.");
            }
          } catch {
            /* keep polling */
          }
        }, 800);
      } catch (e) {
        setError(e.message);
      }
    })();
  }, []);

  const view = steps.length ? steps : STEP_KEYS.map((k) => ({ key: k, status: "pending" }));

  return (
    <div className="flex flex-1 flex-col justify-center p-6">
      <div className="mb-8 text-center">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-brand-100 text-brand-600">
          <Spinner className="h-7 w-7" />
        </div>
        <h2 className="text-xl font-bold text-neutral-800">{t("add.processingTitle")}</h2>
        <p className="mt-1 text-sm text-neutral-500">{t("add.processingSub")}</p>
      </div>
      <div className="space-y-3">
        {view.map((s) => (
          <div key={s.key} className="flex items-center gap-3 rounded-xl bg-white p-3 shadow-sm">
            <span className="flex h-6 w-6 items-center justify-center">
              {s.status === "done" ? (
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
                  <IconCheck size={16} stroke={3} />
                </span>
              ) : s.status === "running" ? (
                <Spinner />
              ) : (
                <span className="h-3 w-3 rounded-full border-2 border-neutral-300" />
              )}
            </span>
            <span
              className={`font-medium ${
                s.status === "done"
                  ? "text-neutral-700"
                  : s.status === "running"
                  ? "text-brand-600"
                  : "text-neutral-400"
              }`}
            >
              {t(`steps.${s.key}`)}
            </span>
          </div>
        ))}
      </div>
      {error && (
        <div className="mt-6 rounded-xl bg-rose-50 p-4 text-center text-sm text-rose-700">{error}</div>
      )}
    </div>
  );
}
