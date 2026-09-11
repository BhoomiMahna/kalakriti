import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api.js";
import { Spinner } from "../components/ui.jsx";

const THEME = {
  amazon: {
    name: "Amazon.in",
    bar: "#131921",
    accent: "#febd69",
    cta: "#ffd814",
    ctaText: "#0f1111",
    idLabel: "Listing ID",
  },
  ondc: {
    name: "ONDC Network",
    bar: "#1b5e5a",
    accent: "#7ac6a0",
    cta: "#1b8f6a",
    ctaText: "#ffffff",
    idLabel: "Catalog ID",
  },
};

export default function DemoListing() {
  const { channel, externalId } = useParams();
  const t = THEME[channel] || THEME.amazon;
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [active, setActive] = useState(0);

  useEffect(() => {
    api.publicListing(externalId).then(setData).catch((e) => setError(e.message));
  }, [externalId]);

  if (error)
    return <Centered>Listing not found. It may not have been published yet.</Centered>;
  if (!data)
    return (
      <Centered>
        <Spinner className="h-8 w-8" />
      </Centered>
    );

  const images = data.images?.length ? data.images : [];
  const price = data.price ? `₹${Number(data.price).toLocaleString("en-IN")}` : "";

  return (
    <div className="min-h-screen bg-white">
      {/* Demo banner */}
      <div className="bg-amber-400 py-1.5 text-center text-xs font-bold text-amber-900">
        DEMO ENVIRONMENT — simulated {t.name} listing, not a real live listing
      </div>

      {/* Marketplace top bar */}
      <div className="flex items-center gap-2 px-4 py-3 text-white" style={{ background: t.bar }}>
        <span className="text-lg font-extrabold" style={{ color: t.accent }}>
          {t.name}
        </span>
        <div className="ml-2 hidden flex-1 items-center rounded bg-white px-3 py-1.5 text-sm text-neutral-500 sm:flex">
          Search {t.name}
        </div>
      </div>

      <div className="mx-auto max-w-3xl p-4">
        <div className="grid gap-6 md:grid-cols-2">
          {/* Gallery */}
          <div>
            <div className="aspect-square overflow-hidden rounded-lg border border-neutral-200 bg-neutral-50">
              {images[active] ? (
                <img src={images[active]} alt="" className="h-full w-full object-cover" />
              ) : null}
            </div>
            <div className="mt-2 flex gap-2">
              {images.map((im, i) => (
                <button
                  key={i}
                  onClick={() => setActive(i)}
                  className={`h-14 w-14 overflow-hidden rounded border-2 ${
                    active === i ? "border-brand-500" : "border-neutral-200"
                  }`}
                >
                  <img src={im} alt="" className="h-full w-full object-cover" />
                </button>
              ))}
            </div>
          </div>

          {/* Info */}
          <div>
            <h1 className="text-xl font-semibold text-neutral-900">{data.title}</h1>
            <p className="mt-1 text-sm" style={{ color: t.bar }}>
              by {data.artisan_name || "Independent Artisan"}
              {data.artisan_location ? ` · ${data.artisan_location}` : ""}
            </p>
            <div className="mt-3 flex items-baseline gap-1">
              <span className="text-sm text-neutral-500">₹</span>
              <span className="text-3xl font-bold text-neutral-900">
                {price.replace("₹", "")}
              </span>
            </div>
            <p className="mt-1 text-xs text-neutral-500">Inclusive of all taxes</p>

            {data.short_description && (
              <p className="mt-3 text-sm text-neutral-700">{data.short_description}</p>
            )}

            <div className="mt-4 space-y-2">
              <button
                className="w-full rounded-full py-2.5 text-sm font-bold"
                style={{ background: t.cta, color: t.ctaText }}
              >
                Add to Cart
              </button>
              <button
                className="w-full rounded-full border py-2.5 text-sm font-bold"
                style={{ borderColor: t.bar, color: t.bar }}
              >
                Buy Now
              </button>
            </div>

            <p className="mt-3 text-xs text-neutral-400">
              {t.idLabel}: <span className="font-mono font-semibold">{externalId}</span>
            </p>
          </div>
        </div>

        {/* Details */}
        {(data.material || data.dimensions || data.category) && (
          <div className="mt-6 rounded-lg border border-neutral-200 p-4">
            <h2 className="mb-2 font-semibold text-neutral-800">Product details</h2>
            <dl className="grid grid-cols-2 gap-y-1 text-sm">
              {data.category && <Row k="Category" v={data.category} />}
              {data.material && <Row k="Material" v={data.material} />}
              {data.dimensions && <Row k="Dimensions" v={data.dimensions} />}
            </dl>
          </div>
        )}

        {data.highlights?.length > 0 && (
          <div className="mt-4 rounded-lg border border-neutral-200 p-4">
            <h2 className="mb-2 font-semibold text-neutral-800">About this item</h2>
            <ul className="list-disc space-y-1 pl-5 text-sm text-neutral-700">
              {data.highlights.map((h, i) => (
                <li key={i}>{h}</li>
              ))}
            </ul>
          </div>
        )}

        {data.long_description && (
          <div className="mt-4 rounded-lg border border-neutral-200 p-4">
            <h2 className="mb-2 font-semibold text-neutral-800">Description</h2>
            <p className="whitespace-pre-line text-sm text-neutral-700">{data.long_description}</p>
          </div>
        )}

        {data.artisan_story && (
          <div className="mt-4 rounded-lg border border-neutral-200 bg-brand-50/40 p-4">
            <h2 className="mb-2 font-semibold text-brand-700">About the Artisan</h2>
            <p className="whitespace-pre-line text-sm text-neutral-700">{data.artisan_story}</p>
          </div>
        )}

        <p className="my-8 text-center text-xs text-neutral-400">
          This is a simulated marketplace page for demonstration. It is not affiliated with{" "}
          {t.name}.
        </p>
      </div>
    </div>
  );
}

function Row({ k, v }) {
  return (
    <>
      <dt className="text-neutral-500">{k}</dt>
      <dd className="font-medium text-neutral-800">{v}</dd>
    </>
  );
}

function Centered({ children }) {
  return (
    <div className="flex min-h-screen items-center justify-center p-6 text-center text-neutral-500">
      {children}
    </div>
  );
}
