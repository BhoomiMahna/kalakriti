import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LANGUAGES, useI18n } from "../lib/i18n.jsx";
import { Logo, IconCheck } from "../components/icons.jsx";
import Speak from "../components/Speak.jsx";

export default function LanguageSelect() {
  const nav = useNavigate();
  const { lang, setLang, t } = useI18n();
  const [choice, setChoice] = useState(lang || "hi");

  function cont() {
    setLang(choice);
    nav("/login", { replace: true });
  }

  return (
    <div className="flex flex-1 flex-col justify-center px-6 py-10">
      <div className="mb-8 text-center">
        <div className="mb-4 flex justify-center">
          <Logo size={56} />
        </div>
        <h1 className="flex items-center justify-center gap-1 text-2xl font-extrabold text-neutral-800">
          {t("lang.title")}
          <Speak text={t("lang.title")} />
        </h1>
        <p className="mt-1 text-sm text-neutral-500">Choose your language · भाषा चुनें · ਭਾਸ਼ਾ ਚੁਣੋ</p>
      </div>

      <div className="space-y-3">
        {LANGUAGES.map((l) => (
          <button
            key={l.code}
            onClick={() => setChoice(l.code)}
            className={`flex w-full items-center justify-between rounded-2xl border-2 px-5 py-4 text-left ${
              choice === l.code
                ? "border-brand-500 bg-brand-50"
                : "border-black/10 bg-white"
            }`}
          >
            <span>
              <span className="block text-xl font-bold text-neutral-800">{l.label}</span>
              <span className="block text-sm text-neutral-400">{l.sub}</span>
            </span>
            {choice === l.code && (
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-500 text-white">
                <IconCheck size={16} stroke={3} />
              </span>
            )}
          </button>
        ))}
      </div>

      <button className="btn-primary mt-8" onClick={cont}>
        {t("lang.continue")}
      </button>
    </div>
  );
}
