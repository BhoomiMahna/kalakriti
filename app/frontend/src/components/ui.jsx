import { NavLink } from "react-router-dom";
import { IconHome, IconPlus, IconUser, IconBox, IconReceipt } from "./icons.jsx";
import { useI18n } from "../lib/i18n.jsx";
import Speak from "./Speak.jsx";

export function Spinner({ className = "" }) {
  return (
    <div
      className={`inline-block h-5 w-5 animate-spin rounded-full border-2 border-brand-200 border-t-brand-500 ${className}`}
    />
  );
}

export function Header({ title, right = null, back = null }) {
  return (
    <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-beige bg-cream/90 px-4 py-3 backdrop-blur">
      {back}
      <h1 className="flex-1 truncate text-lg font-bold text-neutral-800">{title}</h1>
      {right}
    </header>
  );
}

const STATUS_STYLE = {
  DRAFT: "bg-neutral-100 text-neutral-600",
  AI_PROCESSING: "bg-amber-100 text-amber-700",
  READY_FOR_REVIEW: "bg-blue-100 text-blue-700",
  APPROVED: "bg-indigo-100 text-indigo-700",
  PUBLISHING: "bg-amber-100 text-amber-700",
  LIVE: "bg-emerald-100 text-emerald-700",
  FAILED: "bg-rose-100 text-rose-700",
};
export function StatusPill({ status }) {
  const label = (status || "").replaceAll("_", " ").toLowerCase();
  return (
    <span
      className={`rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${
        STATUS_STYLE[status] || "bg-neutral-100 text-neutral-600"
      }`}
    >
      {label}
    </span>
  );
}

const CH_STATE = {
  LIVE: { t: "Live", c: "text-emerald-700", dot: "bg-emerald-500" },
  PROCESSING: { t: "Publishing…", c: "text-amber-700", dot: "bg-amber-500" },
  PENDING: { t: "Queued", c: "text-neutral-500", dot: "bg-neutral-300" },
  FAILED: { t: "Failed", c: "text-rose-700", dot: "bg-rose-500" },
  NEEDS_ATTENTION: { t: "Needs attention", c: "text-amber-700", dot: "bg-amber-500" },
};
export function ChannelRow({ channel, onRetry }) {
  const { t } = useI18n();
  const s = CH_STATE[channel.status] || CH_STATE.PENDING;
  const isDemo = (channel.listing_url || "").includes("/demo/");
  return (
    <div className="flex items-start justify-between gap-2 py-2">
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 rounded-full ${s.dot}`} />
        <span className="font-medium capitalize text-neutral-700">{channel.channel}</span>
      </div>
      <div className="text-right">
        <span className={`text-sm font-semibold ${s.c}`}>
          {s.t}
          {isDemo && channel.status === "LIVE" && (
            <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-amber-700">
              demo
            </span>
          )}
        </span>
        {channel.external_product_id && channel.status === "LIVE" && (
          <p className="mt-0.5 font-mono text-xs text-neutral-400">{channel.external_product_id}</p>
        )}
        {channel.error_reason && (
          <p className="mt-0.5 max-w-[12rem] text-xs text-neutral-500">{channel.error_reason}</p>
        )}
        {channel.listing_url && channel.status === "LIVE" && (
          <a
            href={`#${channel.listing_url}`}
            target="_blank"
            rel="noreferrer"
            className="mt-1 inline-block rounded-lg bg-brand-500 px-3 py-1 text-xs font-semibold text-white"
          >
            {t("review.viewListing", { channel: channel.channel })}
          </a>
        )}
        {(channel.status === "FAILED" || channel.status === "NEEDS_ATTENTION") && onRetry && (
          <button
            onClick={() => onRetry(channel.channel)}
            className="mt-1 rounded-lg bg-brand-50 px-2 py-1 text-xs font-semibold text-brand-700"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}

export function BottomNav() {
  const { t } = useI18n();
  const item = "flex flex-1 flex-col items-center gap-1 py-2.5 text-[11px] font-medium";
  const active = ({ isActive }) =>
    `${item} ${isActive ? "text-brand-600" : "text-neutral-400"}`;
  return (
    <nav className="sticky bottom-0 z-10 flex items-center border-t border-black/5 bg-white">
      <NavLink to="/" end className={active}>
        <IconHome size={22} />
        {t("nav.home")}
      </NavLink>
      <NavLink to="/products" className={active}>
        <IconBox size={22} />
        {t("nav.products")}
      </NavLink>
      <NavLink to="/add" className="flex flex-1 flex-col items-center">
        <span className="-mt-6 flex h-14 w-14 items-center justify-center rounded-full bg-brand-500 text-white shadow-lg">
          <IconPlus size={26} />
        </span>
        <span className="mt-0.5 text-[11px] font-medium text-brand-600">{t("nav.add")}</span>
      </NavLink>
      <NavLink to="/orders" className={active}>
        <IconReceipt size={22} />
        {t("nav.orders")}
      </NavLink>
      <NavLink to="/profile" className={active}>
        <IconUser size={22} />
        {t("nav.profile")}
      </NavLink>
    </nav>
  );
}

export function Empty({ title, subtitle, action }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
      <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50 text-brand-400">
        <IconBox size={30} />
      </div>
      <div className="flex items-center gap-1">
        <h3 className="text-lg font-bold text-neutral-700">{title}</h3>
        <Speak text={`${title}. ${subtitle || ""}`} />
      </div>
      {subtitle && <p className="mt-1 text-sm text-neutral-500">{subtitle}</p>}
      {action && <div className="mt-5 w-full">{action}</div>}
    </div>
  );
}
