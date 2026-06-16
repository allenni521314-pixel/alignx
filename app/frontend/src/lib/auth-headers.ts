import { AUTH_TOKEN_KEY } from "@/lib/auth-session";

/**
 * Shared utility to get authentication headers for API calls.
 * AlignX beta user data is keyed by email-code auth only. Do not silently fall
 * back to legacy SDK tokens, because that can attach requests to another
 * historical user_id in the same browser.
 */
export function getAuthHeaders(): Record<string, string> {
  if (import.meta.env.DEV) {
    return { Authorization: "Bearer dev-local-token" };
  }
  const alignxToken = localStorage.getItem(AUTH_TOKEN_KEY);
  if (alignxToken) {
    return { Authorization: `Bearer ${alignxToken}` };
  }

  return {};
}

/**
 * Get the raw token string (for non-axios usage).
 */
export function getAuthToken(): string | null {
  return localStorage.getItem(AUTH_TOKEN_KEY) || (import.meta.env.DEV ? "dev-local-token" : null);
}
