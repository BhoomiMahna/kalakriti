import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";
import { BottomNav, Empty, Header, Spinner } from "../components/ui.jsx";
import { IconPlus } from "../components/icons.jsx";
import { useI18n } from "../lib/i18n.jsx";
import ProductCard from "../components/ProductCard.jsx";

export default function Products() {
  const nav = useNavigate();
  const { t } = useI18n();
  const [products, setProducts] = useState(null);

  async function load() {
    setProducts(await api.listProducts());
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  return (
    <>
      <Header title={t("products.title")} />
      <div className="flex-1 space-y-3 p-4 pb-28">
        {products === null ? (
          <div className="flex justify-center py-10">
            <Spinner className="h-7 w-7" />
          </div>
        ) : products.length === 0 ? (
          <Empty
            title={t("products.empty")}
            subtitle={t("products.emptySub")}
            action={
              <button
                className="btn-primary flex items-center justify-center gap-2"
                onClick={() => nav("/add")}
              >
                <IconPlus size={20} /> {t("products.add")}
              </button>
            }
          />
        ) : (
          products.map((p) => <ProductCard key={p.id} p={p} />)
        )}
      </div>
      <BottomNav />
    </>
  );
}
