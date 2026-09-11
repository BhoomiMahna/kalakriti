import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";
import { useI18n } from "../lib/i18n.jsx";
import { BottomNav, Header, Spinner } from "../components/ui.jsx";
import { IconChevronLeft } from "../components/icons.jsx";

const STATUS_STYLE = {
  DEMO_PUBLISHED: "bg-emerald-100 text-emerald-700",
  PUBLISHED: "bg-emerald-100 text-emerald-700",
  SCHEDULED: "bg-blue-100 text-blue-700",
  HELD_BACK: "bg-amber-100 text-amber-700",
  UNSAFE: "bg-rose-100 text-rose-700",
  FAILED: "bg-rose-100 text-rose-700",
  EVALUATING: "bg-neutral-100 text-neutral-600",
};

function Stat({ label, value, accent }) {
  return (
    <div className="flex-1 rounded-2xl bg-white p-3 text-center shadow-sm">
      <div className={`text-2xl font-extrabold ${accent || "text-neutral-800"}`}>{value}</div>
      <div className="mt-0.5 text-[11px] font-medium text-neutral-500">{label}</div>
    </div>
  );
}

export default function InstagramAdmin() {
  const nav = useNavigate();
  const { t } = useI18n();
  const [ov, setOv] = useState(null);
  const [posts, setPosts] = useState([]);
  const [busy, setBusy] = useState("");

  async function load() {
    const [o, p] = await Promise.all([api.igOverview(), api.igPosts()]);
    setOv(o);
    setPosts(p);
  }
  useEffect(() => {
    load();
    const timer = setInterval(load, 6000);
    return () => clearInterval(timer);
  }, []);

  async function simulate(id) {
    setBusy(id);
    try {
      await api.igSimulate(id);
      await load();
    } finally {
      setBusy("");
    }
  }

  const fmtTime = (s) =>
    s ? new Date(s).toLocaleString([], { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";

  return (
    <>
      <Header
        title={t("iga.title")}
        back={
          <button onClick={() => nav("/profile")} className="text-neutral-500">
            <IconChevronLeft />
          </button>
        }
      />
      <div className="flex-1 space-y-4 p-4 pb-28">
        <p className="text-xs text-neutral-500">{t("iga.subtitle")}</p>
        {ov?.demo_mode && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-center text-xs font-semibold text-amber-700">
            {t("iga.demo")}
          </div>
        )}

        {!ov ? (
          <div className="flex justify-center py-10">
            <Spinner className="h-7 w-7" />
          </div>
        ) : (
          <>
            <div className="flex gap-2">
              <Stat label={t("iga.evaluated")} value={ov.evaluated} />
              <Stat label={t("iga.selected")} value={ov.selected} accent="text-emerald-600" />
              <Stat label={t("iga.held")} value={ov.held} accent="text-amber-600" />
              <Stat label={t("iga.failed")} value={ov.failed} accent="text-rose-600" />
            </div>
            <div className="card flex items-center justify-between">
              <span className="text-sm text-neutral-500">{t("iga.nextPost")}</span>
              <span className="font-semibold text-neutral-800">{fmtTime(ov.next_post_time)}</span>
            </div>

            <p className="text-sm font-semibold text-neutral-500">{t("iga.recent")}</p>
            {posts.length === 0 ? (
              <p className="py-8 text-center text-sm text-neutral-400">{t("iga.none")}</p>
            ) : (
              <div className="space-y-3">
                {posts.map((p) => (
                  <div key={p.id} className="card">
                    <div className="flex gap-3">
                      <div className="h-16 w-16 flex-shrink-0 overflow-hidden rounded-xl bg-neutral-100">
                        {(p.image_urls || [])[0] && (
                          <img src={p.image_urls[0]} alt="" className="h-full w-full object-cover" />
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <h3 className="truncate text-sm font-semibold text-neutral-800">
                            {p.product_title || "Product"}
                          </h3>
                          <span
                            className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                              STATUS_STYLE[p.status] || "bg-neutral-100 text-neutral-600"
                            }`}
                          >
                            {p.status.replace("_", " ")}
                          </span>
                        </div>
                        <div className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-neutral-500">
                          {p.score != null && <span>Score {(p.score * 100).toFixed(0)}%</span>}
                          <span>{p.safety_safe ? "Safety ✓" : "Safety ⚠"}</span>
                          {p.layout_type && <span>{p.layout_type.replace("_", " ")}</span>}
                          {p.scheduled_time && <span>{fmtTime(p.scheduled_time)}</span>}
                          {p.engagement && (
                            <span className="font-semibold text-emerald-600">
                              ♥ {p.engagement.likes} · {p.engagement.reach} reach
                            </span>
                          )}
                        </div>
                        {p.caption_text && (
                          <p className="mt-1 line-clamp-2 text-xs text-neutral-500">{p.caption_text}</p>
                        )}
                      </div>
                    </div>
                    <div className="mt-2 flex gap-2">
                      {p.permalink && (p.status === "DEMO_PUBLISHED" || p.status === "PUBLISHED") && (
                        <a
                          href={p.permalink.startsWith("/") ? `#${p.permalink}` : p.permalink}
                          target="_blank"
                          rel="noreferrer"
                          className="rounded-lg bg-gradient-to-tr from-[#F58529] to-[#8134AF] px-3 py-1 text-xs font-semibold text-white"
                        >
                          {t("social.viewPost")}
                        </a>
                      )}
                      {(p.status === "DEMO_PUBLISHED" || p.status === "PUBLISHED") && (
                        <button
                          onClick={() => simulate(p.id)}
                          disabled={busy === p.id}
                          className="rounded-lg bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700"
                        >
                          {busy === p.id ? "…" : t("iga.simulate")}
                        </button>
                      )}
                      {p.error && (p.status === "HELD_BACK" || p.status === "UNSAFE" || p.status === "FAILED") && (
                        <span className="text-[11px] text-neutral-400">{p.error}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
      <BottomNav />
    </>
  );
}
