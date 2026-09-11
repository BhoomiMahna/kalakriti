import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/useAuth.jsx";
import { useI18n } from "../lib/i18n.jsx";
import { Spinner } from "../components/ui.jsx";
import { Logo } from "../components/icons.jsx";
import Speak from "../components/Speak.jsx";

export default function Login() {
  const nav = useNavigate();
  const { login } = useAuth();
  const { t, lang } = useI18n();
  const [step, setStep] = useState("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [devOtp, setDevOtp] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function sendOtp() {
    setErr("");
    if (phone.replace(/\D/g, "").length < 8) return setErr(t("login.invalidPhone"));
    setBusy(true);
    try {
      const r = await api.requestOtp(phone);
      setDevOtp(r.dev_otp || null);
      if (r.dev_otp) setCode(r.dev_otp);
      setStep("otp");
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function verify() {
    setErr("");
    setBusy(true);
    try {
      const r = await api.verifyOtp(phone, code);
      // persist chosen language onto the profile
      login(r.access_token, r.artisan);
      if (r.is_new || !r.artisan.preferred_language) {
        try { await api.updateMe({ preferred_language: lang }); } catch { /* ignore */ }
      }
      nav(r.is_new || !r.artisan.ready_to_sell ? "/onboarding" : "/", { replace: true });
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col justify-center px-6 py-10">
      <div className="mb-10 text-center">
        <div className="mb-4 flex justify-center">
          <Logo size={64} />
        </div>
        <h1 className="text-3xl font-extrabold text-brand-700">Kalakriti</h1>
        <p className="mt-2 text-neutral-500">{t("login.tagline")}</p>
      </div>

      {step === "phone" ? (
        <div className="space-y-4">
          <div>
            <div className="mb-1 flex items-center gap-1">
              <label className="label mb-0">{t("login.enterMobile")}</label>
              <Speak text={t("login.enterMobile")} />
            </div>
            <input
              className="input text-xl tracking-wide"
              inputMode="tel"
              placeholder="+91 98765 43210"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          </div>
          {err && <p className="text-sm text-rose-600">{err}</p>}
          <button className="btn-primary" onClick={sendOtp} disabled={busy}>
            {busy ? <Spinner /> : t("login.sendOtp")}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <div className="mb-1 flex items-center gap-1">
              <label className="label mb-0">{t("login.enterOtp", { phone })}</label>
              <Speak text={t("login.enterOtp", { phone })} />
            </div>
            <input
              className="input text-center text-2xl tracking-[0.5em]"
              inputMode="numeric"
              maxLength={6}
              placeholder="______"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            />
          </div>
          {devOtp && (
            <p className="rounded-xl bg-amber-50 p-2 text-center text-sm text-amber-700">
              {t("login.devOtp", { otp: devOtp })}
            </p>
          )}
          {err && <p className="text-sm text-rose-600">{err}</p>}
          <button className="btn-primary" onClick={verify} disabled={busy || code.length < 6}>
            {busy ? <Spinner /> : t("login.verify")}
          </button>
          <button className="btn-secondary" onClick={() => setStep("phone")}>
            {t("login.changeNumber")}
          </button>
        </div>
      )}
    </div>
  );
}
