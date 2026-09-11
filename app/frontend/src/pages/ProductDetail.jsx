import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../lib/api.js";
import { useI18n } from "../lib/i18n.jsx";
import { ChannelRow, Header, Spinner, StatusPill } from "../components/ui.jsx";
import { IconAlert, IconChevronLeft, IconSend } from "../components/icons.jsx";
import Speak from "../components/Speak.jsx";

export default function ProductDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { t } = useI18n();
  const [p, setP] = useState(null);
  const [ig, setIg] = useState(null);
  const [price, setPrice] = useState("");
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const pollRef = useRef(null);

  async function load() {
    const data = await api.getProduct(id);
    setP(data);
    api.productInstagram(id).then(setIg).catch(() => {});
    if (price === "") setPrice(data.price ?? data.suggested_price ?? "");
    const inFlight =
      ["AI_PROCESSING", "PUBLISHING"].includes(data.status) ||
      (data.channels || []).some((c) => c.status === "PROCESSING");
    if (inFlight && !pollRef.current) {
      pollRef.current = setInterval(load, 1500);
    } else if (!inFlight && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }
  useEffect(() => {
    load();
    return () => pollRef.current && clearInterval(pollRef.current);
  }, [id]);

  const Back = () => (
    <button onClick={() => nav("/")} className="text-neutral-500">
      <IconChevronLeft />
    </button>
  );

  if (!p)
    return (
      <>
        <Header title={t("review.title")} back={<Back />} />
        <div className="flex flex-1 justify-center py-16">
          <Spinner className="h-8 w-8" />
        </div>
      </>
    );

  async function savePrice() {
    setBusy("price");
    try {
      setP(await api.setPrice(id, Number(price)));
    } finally {
      setBusy("");
    }
  }
  async function useSuggested() {
    if (p.suggested_price == null) return;
    setPrice(String(p.suggested_price));
    setBusy("price");
    try {
      setP(await api.setPrice(id, Number(p.suggested_price)));
    } finally {
      setBusy("");
    }
  }
  async function publish() {
    setErr("");
    setBusy("publish");
    try {
      if (p.status === "READY_FOR_REVIEW") await api.approve(id);
      await api.publish(id, ["amazon", "ondc"]);
      await load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy("");
    }
  }
  async function retry(channel) {
    await api.retryChannel(id, channel);
    load();
  }

  const gen = p.generated_images || {};
  const statuses = gen.statuses || {};
  const orig = (p.original_images || [])[0];
  const shots = [
    { key: "hero", label: t("review.hero"), url: gen.hero },
    { key: "lifestyle", label: t("review.lifestyle"), url: gen.lifestyle },
    { key: "detail", label: t("review.detail"), url: gen.detail },
  ].map((s) => ({ ...s, status: statuses[s.key] || (s.url ? "ready" : "failed") }));
  const hero = shots.find((s) => s.key === "hero" && s.url);
  const anyFailed = shots.some((s) => s.status === "failed");
  const hasAny = shots.some((s) => s.url);
  const isGenerated = ["gemini", "openai", "flux_url", "demo"].includes(gen.mode);
  const isPreview = gen.mode === "isolate";
  const sectionTitle = isGenerated ? t("review.aiPhotoshoot") : t("photoshoot.previewTitle");
  const afterLabel = isGenerated ? t("photoshoot.after") : t("photoshoot.previewAfter");
  const modeLabel = isGenerated ? t("photoshoot.generated") : isPreview ? t("photoshoot.previewAfter") : null;
  const processing = p.status === "AI_PROCESSING";
  const inr = (n) => `₹${Number(n).toLocaleString("en-IN")}`;

  async function retryPhotoshoot() {
    setBusy("photoshoot");
    try {
      setP(await api.regeneratePhotoshoot(id));
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy("");
    }
  }

  return (
    <>
      <Header title={t("review.title")} back={<Back />} right={<StatusPill status={p.status} />} />
      <div className="flex-1 space-y-4 p-4 pb-28">
        {processing && (
          <div className="rounded-xl bg-amber-50 p-3 text-center text-sm text-amber-700">
            {t("review.processing")}
          </div>
        )}

        {/* AI product photoshoot */}
        {processing ? (
          <div className="flex aspect-video items-center justify-center rounded-xl bg-neutral-100">
            <Spinner />
          </div>
        ) : (
          <div>
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm font-semibold text-neutral-500">{sectionTitle}</p>
              {modeLabel && (
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                    isGenerated ? "bg-brand-50 text-brand-700" : "bg-amber-100 text-amber-700"
                  }`}
                >
                  {modeLabel}
                </span>
              )}
            </div>

            {/* Before -> After */}
            {orig && hero && (
              <div className="mb-2 grid grid-cols-[1fr_auto_1fr] items-center gap-2">
                <figure>
                  <img src={orig} alt="" className="aspect-square w-full rounded-xl object-cover opacity-90" />
                  <figcaption className="mt-0.5 text-center text-[11px] text-neutral-400">{t("photoshoot.before")}</figcaption>
                </figure>
                <span className="text-neutral-300">→</span>
                <figure>
                  <img src={hero.url} alt="" className="aspect-square w-full rounded-xl object-cover ring-2 ring-brand-300" />
                  <figcaption className="mt-0.5 text-center text-[11px] font-semibold text-brand-500">{afterLabel}</figcaption>
                </figure>
              </div>
            )}

            {isPreview && hasAny && (
              <p className="mb-2 rounded-lg bg-amber-50 p-2 text-[11px] text-amber-700">
                {t("photoshoot.previewNote")}
              </p>
            )}

            {/* Three shots with per-shot status */}
            <div className="grid grid-cols-3 gap-2">
              {shots.map((s) => (
                <figure key={s.key}>
                  {s.url ? (
                    <img src={s.url} alt={s.label} className="aspect-square w-full rounded-xl object-cover" />
                  ) : (
                    <div className="flex aspect-square w-full flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-rose-200 bg-rose-50 p-2 text-center">
                      <IconAlert size={16} className="text-rose-400" />
                      <span className="text-[10px] font-medium text-rose-500">{t("photoshoot.failed")}</span>
                    </div>
                  )}
                  <figcaption className="mt-0.5 text-center text-[11px] text-neutral-400">{s.label}</figcaption>
                </figure>
              ))}
            </div>

            {!hasAny && orig && (
              <div className="mt-2">
                <p className="mb-1 text-[11px] text-neutral-400">{t("photoshoot.original")}</p>
                <img src={orig} alt="" className="aspect-square w-full rounded-xl object-cover" />
              </div>
            )}

            {(anyFailed || !hasAny) && (
              <button
                onClick={retryPhotoshoot}
                disabled={busy === "photoshoot"}
                className="btn-chip mt-2 w-full py-2.5 text-sm"
              >
                {busy === "photoshoot" ? <Spinner /> : t("photoshoot.retry")}
              </button>
            )}
          </div>
        )}

        {p.transcription && (
          <div className="card">
            <div className="mb-1 flex items-center justify-between">
              <p className="text-sm font-semibold text-brand-700">{t("review.whatYouTold")}</p>
              <Speak text={p.transcription} />
            </div>
            <p className="text-sm italic text-neutral-500">“{p.transcription}”</p>
          </div>
        )}

        {/* Listing content */}
        <div className="card space-y-2">
          <div className="flex items-start justify-between gap-2">
            <h2 className="text-lg font-bold text-neutral-800">{p.title || "…"}</h2>
            {p.long_description && <Speak text={`${p.title}. ${p.long_description}`} />}
          </div>
          <p className="text-sm text-neutral-600">{p.short_description}</p>
          {p.long_description && (
            <p className="whitespace-pre-line text-sm text-neutral-500">{p.long_description}</p>
          )}
          {p.highlights?.length > 0 && (
            <ul className="mt-2 space-y-1 text-sm text-neutral-600">
              {p.highlights.map((h, i) => (
                <li key={i}>• {h}</li>
              ))}
            </ul>
          )}
        </div>

        {p.artisan_story && (
          <div className="card">
            <div className="mb-1 flex items-center justify-between">
              <p className="text-sm font-semibold text-brand-700">{t("review.yourStory")}</p>
              <Speak text={p.artisan_story} />
            </div>
            <p className="whitespace-pre-line text-sm text-neutral-600">{p.artisan_story}</p>
          </div>
        )}

        {p.validation && !p.validation.valid && (
          <div className="flex items-start gap-2 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">
            <IconAlert size={18} className="mt-0.5 flex-shrink-0" />
            <span>{t("review.flagged")}</span>
          </div>
        )}

        {/* Price — visually prominent */}
        <div className="card bg-gradient-to-b from-brand-50 to-white">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-brand-700">{t("price.title")}</p>
            {p.price_reasoning && <Speak text={t("price.basedOn")} />}
          </div>
          {p.suggested_price != null && (
            <div className="mt-2 text-center">
              <div className="text-4xl font-extrabold text-neutral-900">{inr(p.suggested_price)}</div>
              <div className="mt-0.5 text-xs text-neutral-500">{t("price.recommended")}</div>
              {p.price_low != null && (
                <div className="mt-2 inline-block rounded-full bg-white px-3 py-1 text-sm font-semibold text-neutral-600 ring-1 ring-black/5">
                  {t("price.range")}: {inr(p.price_low)} – {inr(p.price_high)}
                </div>
              )}
              <p className="mt-2 text-xs text-neutral-400">{t("price.basedOn")}</p>
              {Number(price) !== Number(p.suggested_price) && (
                <button onClick={useSuggested} disabled={busy === "price"} className="btn-primary mt-3">
                  {t("price.use", { price: Number(p.suggested_price).toLocaleString("en-IN") })}
                </button>
              )}
            </div>
          )}
          <div className="mt-3">
            <label className="label">{t("price.enterOwn")}</label>
            <div className="flex gap-2">
              <div className="flex flex-1 items-center rounded-xl border border-black/10 bg-white px-3">
                <span className="text-neutral-400">₹</span>
                <input
                  className="w-full py-3 pl-1 text-xl font-bold outline-none"
                  inputMode="numeric"
                  value={price}
                  onChange={(e) => setPrice(e.target.value.replace(/\D/g, ""))}
                />
              </div>
              <button
                onClick={savePrice}
                disabled={busy === "price"}
                className="rounded-xl bg-brand-500 px-5 font-semibold text-white"
              >
                {busy === "price" ? <Spinner /> : t("common.save")}
              </button>
            </div>
          </div>
        </div>

        {/* Channels */}
        {p.channels?.length > 0 && (
          <div className="card">
            <p className="mb-1 text-sm font-semibold text-neutral-600">{t("review.marketplaces")}</p>
            {p.channels.map((c) => (
              <ChannelRow key={c.channel} channel={c} onRetry={retry} t={t} />
            ))}
          </div>
        )}

        {/* Social channels (platform automation — artisan just sees status) */}
        {ig && ig.state && ig.state !== "none" && (
          <div className="card">
            <p className="mb-1 text-sm font-semibold text-neutral-600">{t("social.title")}</p>
            <div className="flex items-start gap-2 py-1">
              <span className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-tr from-[#F58529] via-[#DD2A7B] to-[#8134AF] text-white">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3.5" y="3.5" width="17" height="17" rx="5" />
                  <circle cx="12" cy="12" r="4" />
                  <circle cx="17" cy="7" r="1" fill="currentColor" stroke="none" />
                </svg>
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-neutral-700">
                  {ig.state === "queued" && t("social.queued")}
                  {ig.state === "scheduled" && t("social.scheduled")}
                  {ig.state === "posted" && (ig.demo ? t("social.postedDemo") : t("social.posted"))}
                  {ig.state === "held" && t("social.held")}
                </p>
                <p className="text-xs text-neutral-400">{t("social.auto")}</p>
                {ig.permalink && ig.state === "posted" && (
                  <a
                    href={ig.permalink.startsWith("/") ? `#${ig.permalink}` : ig.permalink}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 inline-block rounded-lg bg-gradient-to-tr from-[#F58529] to-[#8134AF] px-3 py-1 text-xs font-semibold text-white"
                  >
                    {t("social.viewPost")}
                  </a>
                )}
              </div>
            </div>
          </div>
        )}

        {err && <p className="text-sm text-rose-600">{err}</p>}
      </div>

      {!processing && (
        <div className="sticky bottom-0 border-t border-black/5 bg-white p-4">
          <button
            className="btn-primary flex items-center justify-center gap-2"
            onClick={publish}
            disabled={busy === "publish" || !p.price}
          >
            {busy === "publish" ? (
              <Spinner />
            ) : (
              <>
                <IconSend size={18} />
                {p.status === "LIVE" ? t("review.resync") : t("review.publish")}
              </>
            )}
          </button>
        </div>
      )}
    </>
  );
}
