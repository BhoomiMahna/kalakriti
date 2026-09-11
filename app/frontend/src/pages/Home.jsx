import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/useAuth.jsx";
import { useI18n } from "../lib/i18n.jsx";
import { BottomNav, Empty, Header, Spinner } from "../components/ui.jsx";
import { IconPlus } from "../components/icons.jsx";
import Speak from "../components/Speak.jsx";
import ProductCard from "../components/ProductCard.jsx";

function Stat({ label, value, accent }) {
  return (
    <div className="flex-1 rounded-2xl bg-white p-4 text-center shadow-sm">
      <div className={`text-2xl font-extrabold ${accent || "text-neutral-800"}`}>{value}</div>
      <div className="mt-0.5 text-xs font-medium text-neutral-500">{label}</div>
    </div>
  );
}

export default function Home() {
  const nav = useNavigate();
  const { artisan } = useAuth();
  const { t } = useI18n();
  const [products, setProducts] = useState(null);
  const [demo, setDemo] = useState(false);

  async function load() {
    setProducts(await api.listProducts());
  }
  useEffect(() => {
    load();
    api.health().then((h) => setDemo(!!h.demo_mode)).catch(() => {});
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const list = products || [];
  const liveCount = list.filter((p) => (p.channels || []).some((c) => c.status === "LIVE")).length;
  const recent = list.slice(0, 4);

  return (
    <>
      <Header
        title={t("home.greeting", { name: artisan?.name?.split(" ")[0] || "Artisan" })}
        right={<Speak text={t("home.greeting", { name: artisan?.name?.split(" ")[0] || "Artisan" })} />}
      />
      <div className="flex-1 space-y-4 p-4 pb-28">
        {demo && (
          <div className="flex items-center justify-between gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-700">
            <span className="flex-1 text-center">{t("home.demoBanner")}</span>
            <Speak text={t("home.demoBanner")} />
          </div>
        )}

        <div className="flex gap-3">
          <Stat label={t("home.yourProducts")} value={list.length} />
          <Stat label={t("home.live")} value={liveCount} accent="text-emerald-600" />
          <Stat label={t("home.orders")} value={0} accent="text-brand-600" />
        </div>

        <button
          className="btn-primary flex items-center justify-center gap-2"
          onClick={() => nav("/add")}
        >
          <IconPlus size={20} /> {t("home.addProduct")}
        </button>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <p className="text-sm font-semibold text-neutral-500">{t("home.recent")}</p>
            {list.length > 4 && (
              <button onClick={() => nav("/products")} className="text-sm font-semibold text-brand-600">
                {t("home.seeAll")}
              </button>
            )}
          </div>
          {products === null ? (
            <div className="flex justify-center py-10">
              <Spinner className="h-7 w-7" />
            </div>
          ) : list.length === 0 ? (
            <Empty
              title={t("home.noProducts")}
              subtitle={t("home.noProductsSub")}
              action={
                <button
                  className="btn-primary flex items-center justify-center gap-2"
                  onClick={() => nav("/add")}
                >
                  <IconPlus size={20} /> {t("home.addFirst")}
                </button>
              }
            />
          ) : (
            <div className="space-y-3">
              {recent.map((p) => (
                <ProductCard key={p.id} p={p} />
              ))}
            </div>
          )}
        </div>
      </div>
      <BottomNav />
    </>
  );
}
