import { Link } from "react-router-dom";
import { IconBox } from "./icons.jsx";
import { StatusPill } from "./ui.jsx";

export default function ProductCard({ p }) {
  const gen = p.generated_images || {};
  const img = gen.hero || (p.enhanced_images || p.original_images || [])[0];
  const live = (p.channels || []).filter((c) => c.status === "LIVE").length;
  return (
    <Link to={`/product/${p.id}`} className="card flex gap-3 active:scale-[0.99]">
      <div className="h-20 w-20 flex-shrink-0 overflow-hidden rounded-xl bg-neutral-100">
        {img ? (
          <img src={img} alt="" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full items-center justify-center text-neutral-300">
            <IconBox size={28} />
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <h3 className="truncate font-semibold text-neutral-800">
            {p.title || "Untitled product"}
          </h3>
          <StatusPill status={p.status} />
        </div>
        {p.price != null && (
          <p className="mt-0.5 font-bold text-brand-700">₹{p.price.toLocaleString("en-IN")}</p>
        )}
        <p className="mt-1 text-xs text-neutral-500">
          {live > 0 ? `Live on ${live} marketplace${live > 1 ? "s" : ""}` : "Not published yet"}
        </p>
      </div>
    </Link>
  );
}
