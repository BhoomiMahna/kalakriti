import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/useAuth.jsx";
import { useI18n, LANGUAGES } from "../lib/i18n.jsx";
import { BottomNav, Header } from "../components/ui.jsx";
import Speak from "../components/Speak.jsx";

export default function Profile() {
  const { artisan, setArtisan, logout } = useAuth();
  const { t, lang, setLang } = useI18n();
  const [form, setForm] = useState({});
  const [channels, setChannels] = useState({});
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (artisan) setForm(artisan);
    api.myChannels().then((c) => setChannels(c.channels || {}));
  }, [artisan]);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function save() {
    const up = await api.updateMe({
      name: form.name,
      craft_category: form.craft_category,
      location: form.location,
      business_name: form.business_name,
    });
    setArtisan(up);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  async function changeLang(code) {
    setLang(code);
    try {
      const up = await api.updateMe({ preferred_language: code });
      setArtisan(up);
    } catch {
      /* ignore */
    }
  }

  const Field = ({ k, field }) => (
    <div>
      <div className="mb-1 flex items-center gap-1">
        <label className="label mb-0">{t(k)}</label>
        <Speak text={t(k)} />
      </div>
      <input className="input" value={form[field] || ""} onChange={set(field)} />
    </div>
  );

  return (
    <>
      <Header title={t("profile.title")} />
      <div className="flex-1 space-y-4 p-4 pb-28">
        <div className="card">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm font-semibold text-neutral-600">{t("profile.completion")}</p>
            <span className="font-bold text-brand-600">{artisan?.profile_completion || 0}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-neutral-100">
            <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${artisan?.profile_completion || 0}%` }} />
          </div>
          {artisan?.ready_to_sell && <p className="mt-2 text-sm text-emerald-600">✓ {t("profile.readyToSell")}</p>}
        </div>

        {/* App language switcher */}
        <div className="card">
          <p className="mb-2 text-sm font-semibold text-neutral-600">{t("profile.language")}</p>
          <div className="grid grid-cols-3 gap-2">
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                onClick={() => changeLang(l.code)}
                className={`rounded-xl border px-2 py-2.5 text-sm font-medium ${
                  lang === l.code ? "border-brand-400 bg-brand-50 text-brand-700" : "border-black/10 bg-white text-neutral-600"
                }`}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>

        <div className="card space-y-3">
          <Field k="profile.name" field="name" />
          <Field k="profile.craft" field="craft_category" />
          <Field k="profile.location" field="location" />
          <Field k="profile.business" field="business_name" />
          <button className="btn-primary" onClick={save}>
            {saved ? `✓ ${t("common.saved")}` : t("profile.save")}
          </button>
        </div>

        <div className="card">
          <p className="mb-2 text-sm font-semibold text-neutral-600">{t("profile.connections")}</p>
          {Object.entries(channels).map(([name, ok]) => (
            <div key={name} className="flex items-center justify-between py-1.5">
              <span className="capitalize text-neutral-700">{name}</span>
              <span className={ok ? "text-sm font-semibold text-emerald-600" : "text-sm text-amber-600"}>
                {ok ? `✓ ${t("profile.connected")}` : t("profile.notConnected")}
              </span>
            </div>
          ))}
          <p className="mt-2 text-xs text-neutral-400">{t("profile.connectNote")}</p>
        </div>

        <div className="card text-sm text-neutral-500">
          <p>{artisan?.phone}</p>
        </div>

        <a
          href="#/instagram"
          className="card flex items-center justify-between active:scale-[0.99]"
        >
          <span className="flex items-center gap-2 text-sm font-semibold text-neutral-700">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-tr from-[#F58529] via-[#DD2A7B] to-[#8134AF] text-white">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3.5" y="3.5" width="17" height="17" rx="5" />
                <circle cx="12" cy="12" r="4" />
                <circle cx="17" cy="7" r="1" fill="currentColor" stroke="none" />
              </svg>
            </span>
            {t("iga.title")}
          </span>
          <span className="text-neutral-300">›</span>
        </a>

        <button className="btn-secondary" onClick={logout}>
          {t("profile.logout")}
        </button>
      </div>
      <BottomNav />
    </>
  );
}
