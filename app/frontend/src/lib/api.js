// Thin API client. Token persisted in localStorage.
const TOKEN_KEY = "artisan_token";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}
export function setToken(t) {
  try {
    if (t) localStorage.setItem(TOKEN_KEY, t);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

async function request(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let payload;
  if (form) {
    payload = form; // FormData — let the browser set the content-type
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(`/api${path}`, { method, headers, body: payload });
  if (res.status === 401) {
    setToken(null);
    if (!path.startsWith("/auth")) window.location.hash = "#/login";
  }
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = data?.detail || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

export const api = {
  requestOtp: (phone) => request("/auth/request-otp", { method: "POST", body: { phone } }),
  verifyOtp: (phone, code) =>
    request("/auth/verify-otp", { method: "POST", body: { phone, code } }),

  me: () => request("/artisans/me"),
  updateMe: (patch) => request("/artisans/me", { method: "PATCH", body: patch }),
  myChannels: () => request("/artisans/me/channels"),

  pricingMeta: () => request("/pricing/metadata"),
  suggestPrice: (inputs) => request("/pricing/suggest", { method: "POST", body: inputs }),

  listProducts: () => request("/products"),
  getProduct: (id) => request(`/products/${id}`),
  latestJob: (id) => request(`/products/${id}/job`),
  createProduct: (form) => request("/products", { method: "POST", form }),
  regeneratePhotoshoot: (id) => request(`/products/${id}/photoshoot`, { method: "POST" }),
  setPrice: (id, price) => request(`/products/${id}/price`, { method: "PATCH", body: { price } }),
  approve: (id) => request(`/products/${id}/approve`, { method: "POST" }),
  publish: (id, channels) =>
    request(`/products/${id}/publish`, { method: "POST", body: { channels } }),
  retryChannel: (id, channel) =>
    request(`/products/${id}/channels/${channel}/retry`, { method: "POST" }),

  transcribe: (form) => request("/transcribe", { method: "POST", form }),
  tts: (text, language) => request("/tts", { method: "POST", body: { text, language } }),

  publicListing: (externalId) => request(`/public/listing/${externalId}`),

  productInstagram: (id) => request(`/products/${id}/instagram`),
  igOverview: () => request("/admin/instagram/overview"),
  igPosts: () => request("/admin/instagram/posts"),
  igSimulate: (postId) =>
    request(`/admin/instagram/posts/${postId}/simulate-engagement`, { method: "POST" }),
  publicIgPost: (externalId) => request(`/public/instagram/post/${externalId}`),

  health: () => request("/admin/health"),
};
