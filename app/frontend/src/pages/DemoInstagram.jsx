import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api.js";
import { Spinner } from "../components/ui.jsx";

export default function DemoInstagram() {
  const { externalId } = useParams();
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [active, setActive] = useState(0);

  useEffect(() => {
    api.publicIgPost(externalId).then(setD).catch((e) => setErr(e.message));
  }, [externalId]);

  if (err) return <Centered>Post not found.</Centered>;
  if (!d)
    return (
      <Centered>
        <Spinner className="h-8 w-8" />
      </Centered>
    );

  const images = d.images?.length ? d.images : [];
  const eng = d.engagement || {};
  const price = d.price ? `₹${Number(d.price).toLocaleString("en-IN")}` : "";

  return (
    <div className="min-h-screen bg-[#fafafa]">
      <div className="bg-amber-400 py-1.5 text-center text-xs font-bold text-amber-900">
        DEMO ENVIRONMENT — simulated Instagram post, not live on Instagram
      </div>

      <div className="mx-auto max-w-md bg-white sm:mt-6 sm:rounded-xl sm:border sm:border-neutral-200 sm:shadow-sm">
        {/* header */}
        <div className="flex items-center gap-2 p-3">
          <div className="h-9 w-9 rounded-full bg-gradient-to-tr from-[#F58529] via-[#DD2A7B] to-[#8134AF] p-[2px]">
            <div className="flex h-full w-full items-center justify-center rounded-full bg-white text-sm font-extrabold text-[#DD2A7B]">
              K
            </div>
          </div>
          <div className="flex-1">
            <div className="text-sm font-semibold text-neutral-900">
              {d.account_handle?.replace("@", "") || "kalakriti.craft"}
            </div>
            <div className="text-[11px] text-neutral-500">Artisan marketplace</div>
          </div>
          <span className="text-xl leading-none text-neutral-400">⋯</span>
        </div>

        {/* image / carousel */}
        <div className="relative aspect-square w-full bg-neutral-100">
          {images[active] && (
            <img src={images[active]} alt="" className="h-full w-full object-cover" />
          )}
          {images.length > 1 && (
            <>
              <div className="absolute right-2 top-2 rounded-full bg-black/60 px-2 py-0.5 text-[11px] font-semibold text-white">
                {active + 1}/{images.length}
              </div>
              <div className="absolute bottom-2 left-1/2 flex -translate-x-1/2 gap-1">
                {images.map((_, i) => (
                  <button
                    key={i}
                    onClick={() => setActive(i)}
                    className={`h-1.5 rounded-full transition-all ${
                      i === active ? "w-4 bg-[#DD2A7B]" : "w-1.5 bg-white/70"
                    }`}
                  />
                ))}
              </div>
            </>
          )}
        </div>

        {/* actions */}
        <div className="flex items-center gap-4 px-3 pt-3 text-neutral-800">
          <Heart /> <Comment /> <Share />
          <span className="ml-auto">
            <Bookmark />
          </span>
        </div>

        {/* likes + caption */}
        <div className="px-3 pb-4 pt-2">
          {eng.likes != null && (
            <div className="text-sm font-semibold text-neutral-900">
              {Number(eng.likes).toLocaleString("en-IN")} likes
            </div>
          )}
          <p className="mt-1 whitespace-pre-line text-sm text-neutral-800">
            <span className="font-semibold">
              {d.account_handle?.replace("@", "") || "kalakriti.craft"}
            </span>{" "}
            {d.caption_text}
            {price && <span className="font-semibold"> — {price}</span>}
          </p>
          {d.call_to_action && (
            <p className="mt-1 text-sm font-medium text-neutral-700">{d.call_to_action}</p>
          )}
          {d.hashtags?.length > 0 && (
            <p className="mt-1 text-sm text-[#385185]">
              {d.hashtags.map((h) => `#${h}`).join(" ")}
            </p>
          )}
          {(eng.comments != null || eng.reach != null) && (
            <div className="mt-2 flex gap-4 text-[11px] uppercase tracking-wide text-neutral-400">
              {eng.comments != null && <span>{eng.comments} comments</span>}
              {eng.reach != null && <span>{Number(eng.reach).toLocaleString("en-IN")} reach</span>}
              {eng.saves != null && <span>{eng.saves} saves</span>}
            </div>
          )}
        </div>
      </div>

      <p className="mx-auto my-6 max-w-md px-4 text-center text-xs text-neutral-400">
        Simulated for demonstration. Not affiliated with Instagram. Posts to the platform's
        single brand account, generated automatically from the artisan's product.
      </p>
    </div>
  );
}

const Heart = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M20.8 8.6c0 4.4-8.8 9.9-8.8 9.9S3.2 13 3.2 8.6A4.6 4.6 0 0 1 12 6.9a4.6 4.6 0 0 1 8.8 1.7z" />
  </svg>
);
const Comment = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M21 11.5a8.5 8.5 0 0 1-12.3 7.6L3 21l1.9-5.7A8.5 8.5 0 1 1 21 11.5z" />
  </svg>
);
const Share = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round">
    <path d="M22 2 11 13M22 2l-7 20-4-9-9-4z" />
  </svg>
);
const Bookmark = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round">
    <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
  </svg>
);

function Centered({ children }) {
  return (
    <div className="flex min-h-screen items-center justify-center p-6 text-center text-neutral-500">
      {children}
    </div>
  );
}
