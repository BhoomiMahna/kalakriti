import { BottomNav, Empty, Header } from "../components/ui.jsx";
import { useI18n } from "../lib/i18n.jsx";

export default function Orders() {
  const { t } = useI18n();
  return (
    <>
      <Header title={t("orders.title")} />
      <div className="flex-1 p-4 pb-28">
        <Empty title={t("orders.empty")} subtitle={t("orders.emptySub")} />
        <p className="mt-4 text-center text-xs text-neutral-400">{t("orders.soon")}</p>
      </div>
      <BottomNav />
    </>
  );
}
