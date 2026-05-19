/**
 * Shared utility to get authentication headers for API calls.
 * Checks multiple token storage locations:
 * 1. "alignx_token" - custom phone-based login
 * 2. "token" - Atoms Cloud SDK / OIDC login
 */
export function getAuthHeaders(): Record<string, string> {
  // Check custom phone login token first
  const alignxToken = localStorage.getItem("alignx_token");
  if (alignxToken) {
    return { Authorization: `Bearer ${alignxToken}` };
  }

  // Check SDK/OIDC token
  const sdkToken = localStorage.getItem("token");
  if (sdkToken) {
    return { Authorization: `Bearer ${sdkToken}` };
  }

  return {};
}

/**
 * Get the raw token string (for non-axios usage).
 */
export function getAuthToken(): string | null {
  return localStorage.getItem("alignx_token") || localStorage.getItem("token") || null;
}