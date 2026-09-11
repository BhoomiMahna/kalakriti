import { createContext, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [artisan, setArtisan] = useState(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    if (!getToken()) {
      setArtisan(null);
      setLoading(false);
      return;
    }
    try {
      setArtisan(await api.me());
    } catch {
      setArtisan(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  function login(token, artisanData) {
    setToken(token);
    setArtisan(artisanData);
  }
  function logout() {
    setToken(null);
    setArtisan(null);
    window.location.hash = "#/login";
  }

  return (
    <AuthCtx.Provider value={{ artisan, setArtisan, loading, login, logout, refresh }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth() {
  return useContext(AuthCtx);
}
