import axios from "axios";
import { toast } from "sonner";

export const AUTH_TOKEN_KEY = "alignx_token";
export const AUTH_USER_KEY = "alignx_user";
export const AUTH_EXPIRED_EVENT = "alignx-auth-expired";

let redirectingForAuth = false;

export function clearAuthStorage() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_USER_KEY);
  localStorage.removeItem("token");
  try {
    delete (window as any).__alignx_token;
  } catch {
    // Ignore non-critical cleanup failures.
  }
}

function inputUrl(input: Parameters<typeof fetch>[0] | string | undefined): string {
  if (!input) return "";
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.toString();
  return input.url || "";
}

function isExcludedAuthEndpoint(url: string): boolean {
  return (
    url.includes("/api/v1/auth/email/send-code") ||
    url.includes("/api/v1/auth/email/login") ||
    url.includes("/api/v1/auth/me") ||
    url.includes("/api/v1/auth/callback") ||
    url.includes("/api/v1/auth/token/exchange")
  );
}

function shouldHandleUnauthorized(url: string): boolean {
  return url.includes("/api/v1/") && !isExcludedAuthEndpoint(url);
}

function redirectToLogin() {
  if (redirectingForAuth || window.location.pathname === "/login") return;
  redirectingForAuth = true;
  const from = `${window.location.pathname}${window.location.search}`;
  const target = from && from !== "/" ? `/login?from=${encodeURIComponent(from)}` : "/login";
  window.setTimeout(() => {
    window.location.href = target;
  }, 120);
}

function handleUnauthorized(url: string, onExpired: () => void) {
  if (!shouldHandleUnauthorized(url)) return;
  clearAuthStorage();
  onExpired();
  window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  toast.warning("登录已过期，请重新登录", { id: "alignx-auth-expired" });
  redirectToLogin();
}

export function installAuthSessionHandlers(onExpired: () => void): () => void {
  const axiosInterceptor = axios.interceptors.response.use(
    (response) => response,
    (error) => {
      const status = error?.response?.status;
      const url = String(error?.config?.url || "");
      if (status === 401) {
        handleUnauthorized(url, onExpired);
      }
      return Promise.reject(error);
    }
  );

  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    const response = await originalFetch(input, init);
    if (response.status === 401) {
      handleUnauthorized(inputUrl(input), onExpired);
    }
    return response;
  };

  return () => {
    axios.interceptors.response.eject(axiosInterceptor);
    window.fetch = originalFetch;
  };
}
