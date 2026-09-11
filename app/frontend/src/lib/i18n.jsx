import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import en from "../locales/en.json";
import hi from "../locales/hi.json";
import pa from "../locales/pa.json";

const DICTS = { en, hi, pa };
export const LANGUAGES = [
  { code: "hi", label: "हिन्दी", sub: "Hindi" },
  { code: "pa", label: "ਪੰਜਾਬੀ", sub: "Punjabi" },
  { code: "en", label: "English", sub: "English" },
];
const KEY = "artisan_lang";

function lookup(dict, path) {
  return path.split(".").reduce((o, k) => (o == null ? undefined : o[k]), dict);
}

const I18nCtx = createContext(null);

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(() => {
    try {
      return localStorage.getItem(KEY) || "";
    } catch {
      return "";
    }
  });

  const setLang = useCallback((code) => {
    setLangState(code);
    try {
      localStorage.setItem(KEY, code);
    } catch {
      /* ignore */
    }
  }, []);

  const t = useCallback(
    (key, vars) => {
      const active = lang || "en";
      let val = lookup(DICTS[active], key);
      if (val == null) val = lookup(DICTS.en, key); // fall back to English
      if (val == null) return key;
      if (vars) {
        Object.entries(vars).forEach(([k, v]) => {
          val = val.replace(new RegExp(`\\{${k}\\}`, "g"), v);
        });
      }
      return val;
    },
    [lang]
  );

  const value = useMemo(() => ({ lang, setLang, t, hasLang: !!lang }), [lang, setLang, t]);
  return <I18nCtx.Provider value={value}>{children}</I18nCtx.Provider>;
}

export function useI18n() {
  return useContext(I18nCtx);
}
