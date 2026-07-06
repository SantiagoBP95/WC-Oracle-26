import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

const ACCESS = "wc_access";
const REFRESH = "wc_refresh";
const PROFILE = "wc_profile";

export const tokenStore = {
  get access() {
    return localStorage.getItem(ACCESS);
  },
  get refresh() {
    return localStorage.getItem(REFRESH);
  },
  get profile() {
    return localStorage.getItem(PROFILE);
  },
  set(access: string, refresh: string, profile?: string) {
    localStorage.setItem(ACCESS, access);
    localStorage.setItem(REFRESH, refresh);
    if (profile) localStorage.setItem(PROFILE, profile);
  },
  clear() {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
    localStorage.removeItem(PROFILE);
  },
};

// baseURL relativo: en dev lo proxya Vite; en prod lo proxya Caddy (Servidor B).
export const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((config) => {
  const token = tokenStore.access;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing: Promise<string> | null = null;

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    if (error.response?.status === 401 && original && !original._retry && tokenStore.refresh) {
      original._retry = true;
      try {
        if (!refreshing) {
          refreshing = axios
            .post("/api/auth/refresh", { refresh_token: tokenStore.refresh })
            .then((res) => {
              tokenStore.set(res.data.access_token, res.data.refresh_token);
              return res.data.access_token as string;
            })
            .finally(() => {
              refreshing = null;
            });
        }
        const newToken = await refreshing;
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      } catch {
        const wasPreview = tokenStore.profile === "preview";
        tokenStore.clear();
        if (wasPreview) {
          location.href = "/upgrade";
        } else if (location.pathname !== "/login") {
          location.href = "/login";
        }
      }
    }
    return Promise.reject(error);
  }
);

export function apiErrorMessage(error: unknown, fallback = "Ocurrió un error"): string {
  const e = error as AxiosError<{ detail?: string }>;
  return e?.response?.data?.detail || e?.message || fallback;
}
