/**
 * Shared API retry utility with exponential backoff.
 * Handles transient DNS/network errors from Atoms Cloud backend.
 */

const RETRYABLE_ERRORS = [
  "dns",
  "balancer",
  "timeout",
  "ECONNREFUSED",
  "ENOTFOUND",
  "network",
  "fetch failed",
  "callback lock",
];

function isRetryableError(error: unknown): boolean {
  const msg =
    (error instanceof Error ? error.message : String(error)).toLowerCase();
  return RETRYABLE_ERRORS.some((keyword) => msg.includes(keyword));
}

/**
 * Execute an async function with retry logic.
 * @param fn - The async function to execute
 * @param options - Retry options
 * @returns The result of the function
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  options: {
    maxRetries?: number;
    baseDelay?: number;
    onRetry?: (attempt: number, error: unknown) => void;
  } = {}
): Promise<T> {
  const { maxRetries = 3, baseDelay = 1000, onRetry } = options;

  let lastError: unknown;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;

      if (attempt < maxRetries && isRetryableError(error)) {
        const delay = baseDelay * Math.pow(2, attempt);
        onRetry?.(attempt + 1, error);
        await new Promise((resolve) => setTimeout(resolve, delay));
        continue;
      }

      throw error;
    }
  }

  throw lastError;
}

/**
 * Get a user-friendly error message from an API error.
 */
export function getApiErrorMessage(error: unknown): string {
  const msg =
    error instanceof Error ? error.message : String(error);

  if (isRetryableError(error)) {
    return "服务器暂时不可用，请稍后重试。如果问题持续，请刷新页面。";
  }

  // Check for HTTP status in axios-style errors
  const axiosError = error as { response?: { status?: number; data?: { message?: string; detail?: string } } };
  if (axiosError?.response?.status === 401) {
    return "登录已过期，请重新登录。";
  }
  if (axiosError?.response?.status === 403) {
    return "没有权限执行此操作。";
  }
  if (axiosError?.response?.status === 404) {
    return "请求的资源不存在。";
  }
  if (axiosError?.response?.status && axiosError.response.status >= 500) {
    return axiosError.response.data?.message || axiosError.response.data?.detail || "服务器错误，请稍后重试。";
  }

  if (msg.includes("500")) {
    return "服务器错误，请稍后重试。";
  }

  return msg || "操作失败，请重试。";
}