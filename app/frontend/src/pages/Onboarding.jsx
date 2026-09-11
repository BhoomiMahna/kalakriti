import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/useAuth.jsx";
import { useI18n, LANGUAGES } from "../lib/i18n.jsx";
import { Header, Spinner } from "../components/ui.jsx";
import Speak from "../components/Speak.jsx";

const CRAFTS = ["Handicraft", "Clothing", "Textile", "Jewelry", "Pottery", "Furniture"];

export default function Onboarding() {
  const nav = useNavigate();
  const { artisan, setArtisan } = useAuth();
  const { t, lang, setLang } = useI18n();
  const [form, setForm] = useState({
    name: artisan?.name || "",
    preferred_language: artisan?.preferred_language || lang || "hi",
    craft_category: artisan?.craft_category || "",
    location: artisan?.location || "",
    business_name: artisan?.business_name || "",
  });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function save() {
    setBusy(true);
    try {
      const updated = await api.updateMe(form);
      setArtisan(updated);
      nav("/", { replace: true });
    } finally {
      setBusy(false);
    }
  }

  const canSave = form.name && form.craft_category && form.location;
  const FieldLabel = ({ k }) => (
    <div className="mb-1 flex items-center gap-1">
      <label className="label mb-0">{t(k)}</label>
      <Speak text={t(k)} />
    </div>
  );

  return (
    <>
      <Header title={t("onboarding.title")} />
      <div className="flex-1 space-y-5 p-4">
        <p className="text-sm text-neutral-500">{t("onboarding.subtitle")}</p>

        <div>
          <FieldLabel k="onboarding.name" />
          <input className="input" value={form.name} onChange={set("name")} placeholder={t("onboarding.namePh")} />
        </div>

        <div>
          <label className="label">{t("onboarding.language")}</label>
          <div className="grid grid-cols-3 gap-2">
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                onClick={() => {
                  setForm({ ...form, preferred_language: l.code });
                  setLang(l.code);
                }}
                className={`rounded-xl border px-2 py-2.5 text-sm font-medium ${
                  form.preferred_language === l.code
                    ? "border-brand-400 bg-brand-50 text-brand-700"
                    : "border-black/10 bg-white text-neutral-600"
                }`}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <FieldLabel k="onboarding.craft" />
          <div className="flex flex-wrap gap-2">
            {CRAFTS.map((c) => (
              <button
                key={c}
                onClick={() => setForm({ ...form, craft_category: c })}
                className={`rounded-full border px-4 py-2 text-sm font-medium ${
                  form.craft_category === c
                    ? "border-brand-400 bg-brand-50 text-brand-700"
                    : "border-black/10 bg-white text-neutral-600"
                }`}
              >
                {t(`crafts.${c}`)}
              </button>
            ))}
          </div>
        </div>

        <div>
          <FieldLabel k="onboarding.location" />
          <input className="input" value={form.location} onChange={set("location")} placeholder={t("onboarding.locationPh")} />
        </div>

        <div>
          <FieldLabel k="onboarding.business" />
          <input className="input" value={form.business_name} onChange={set("business_name")} placeholder={t("onboarding.businessPh")} />
        </div>
      </div>

      <div className="sticky bottom-0 border-t border-black/5 bg-white p-4">
        <button className="btn-primary" onClick={save} disabled={!canSave || busy}>
          {busy ? <Spinner /> : t("onboarding.save")}
        </button>
      </div>
    </>
  );
}
