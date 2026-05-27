// Runtime configuration
let runtimeConfig: {
  API_BASE_URL: string;
} | null = null;

// Configuration loading state
let configLoading = true;

// Default fallback configuration
const defaultConfig = {
  API_BASE_URL: '', // Production-safe same-origin fallback
};

// Function to load runtime configuration
export async function loadRuntimeConfig(): Promise<void> {
  try {
    // Try to load configuration from a config endpoint
    const response = await fetch('/api/config');
    if (response.ok) {
      const contentType = response.headers.get('content-type');
      // Only parse as JSON if the response is actually JSON
      if (contentType && contentType.includes('application/json')) {
        runtimeConfig = await response.json();
      }
    }
  } catch (error) {
    void error;
  } finally {
    configLoading = false;
  }
}

// Get current configuration
export function getConfig() {
  // If config is still loading, return default config to avoid using stale Vite env vars
  if (configLoading) {
    return defaultConfig;
  }

  // First try runtime config (for Lambda)
  if (runtimeConfig) {
    return runtimeConfig;
  }

  // Then try Vite environment variables (for local development)
  if (import.meta.env.VITE_API_BASE_URL) {
    const viteConfig = {
      API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
    };
    return viteConfig;
  }

  // Finally fall back to default
  return defaultConfig;
}

// Dynamic API_BASE_URL getter - this will always return the current config
export function getAPIBaseURL(): string {
  return getConfig().API_BASE_URL;
}

// For backward compatibility, but this should be avoided
// Removed static export to prevent using stale config values
// export const API_BASE_URL = getAPIBaseURL();

export const config = {
  get API_BASE_URL() {
    return getAPIBaseURL();
  },
};
