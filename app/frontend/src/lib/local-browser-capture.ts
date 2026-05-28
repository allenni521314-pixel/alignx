export type LocalCaptureRecord = {
  id: number;
  pageType?: string;
  pageUrl?: string;
  pageTitle?: string;
  capturedAt?: string;
  rawPayload?: {
    url?: string;
    title?: string;
    html?: string;
    text?: string;
    capturedAt?: string;
    platform?: string;
  };
  parsed?: Record<string, unknown>;
  analysis?: Record<string, unknown>;
};

export type AmazonBrowserCaptureResult = {
  status: string;
  source: "user_chrome_extension" | "user_chrome_apple_events" | "local_browser_agent";
  record: LocalCaptureRecord;
};

function getLocalCaptureBaseURL() {
  if (typeof window === "undefined") return "/local-capture";
  const host = window.location.hostname;
  if (host === "localhost" || host === "127.0.0.1") return "/local-capture";
  return "http://127.0.0.1:8787";
}

function extensionBridgeReady() {
  return (
    typeof document !== "undefined" &&
    document.documentElement.getAttribute("data-alignx-capture-bridge") === "ready"
  );
}

function readJson<T>(response: Response): Promise<T | null> {
  return response.json().catch(() => null);
}

async function requestExtensionBridgeCapture(params: {
  asin: string;
  url: string;
}): Promise<AmazonBrowserCaptureResult> {
  if (typeof window === "undefined" || !extensionBridgeReady()) {
    throw new Error("browser_extension_unavailable");
  }

  const requestId = `amazon_capture_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      window.removeEventListener("message", handleMessage);
      reject(new Error("browser_extension_timeout"));
    }, 20_000);

    function handleMessage(event: MessageEvent) {
      if (event.source !== window) return;
      if (event.data?.type !== "ALIGNX_CAPTURE_RESPONSE") return;
      if (event.data?.requestId !== requestId) return;

      window.clearTimeout(timeout);
      window.removeEventListener("message", handleMessage);

      if (!event.data?.ok) {
        reject(new Error(event.data?.error || "browser_extension_capture_failed"));
        return;
      }

      const data = event.data.data as { status?: string; record?: LocalCaptureRecord } | null;
      if (!data?.record?.rawPayload?.html) {
        reject(new Error("browser_extension_empty_html"));
        return;
      }
      resolve({
        status: data.status || "ok",
        source: "user_chrome_extension",
        record: data.record,
      });
    }

    window.addEventListener("message", handleMessage);
    window.postMessage(
      {
        type: "ALIGNX_REQUEST_CAPTURE",
        requestId,
        asin: params.asin,
        url: params.url,
        platform: "amazon",
      },
      "*",
    );
  });
}

async function requestLocalBrowserAgentCapture(params: {
  asin: string;
  url: string;
  marketplace: string;
}): Promise<AmazonBrowserCaptureResult> {
  const response = await fetch(`${getLocalCaptureBaseURL()}/api/capture/browser-agent/capture`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      asin: params.asin,
      url: params.url,
      marketplace: params.marketplace,
      platform: "amazon",
    }),
  });
  const data = await readJson<{ status?: string; record?: LocalCaptureRecord; error?: string }>(response);
  if (response.ok && data?.record?.rawPayload?.html) {
    return {
      status: data.status || "ok",
      source: "local_browser_agent",
      record: data.record,
    };
  }
  throw new Error(data?.error || `local_browser_agent_failed_${response.status}`);
}

async function requestUserChromeCapture(params: {
  url: string;
}): Promise<AmazonBrowserCaptureResult> {
  const response = await fetch(`${getLocalCaptureBaseURL()}/api/capture/user-chrome/capture`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url: params.url,
      platform: "amazon",
    }),
  });
  const data = await readJson<{ status?: string; record?: LocalCaptureRecord; error?: string }>(response);
  if (response.ok && data?.record?.rawPayload?.html) {
    return {
      status: data.status || "ok",
      source: "user_chrome_apple_events",
      record: data.record,
    };
  }
  throw new Error(data?.error || `user_chrome_capture_failed_${response.status}`);
}

export async function captureAmazonProductPage(params: {
  asin: string;
  url: string;
  marketplace: string;
}): Promise<AmazonBrowserCaptureResult> {
  const errors: string[] = [];

  try {
    return await requestExtensionBridgeCapture(params);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (message !== "browser_extension_unavailable") errors.push(message);
  }

  try {
    return await requestUserChromeCapture({ url: params.url });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    errors.push(message);
  }

  try {
    return await requestLocalBrowserAgentCapture(params);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    errors.push(message);
  }

  throw new Error(errors.filter(Boolean).join("; ") || "local_browser_capture_unavailable");
}

export function getCaptureHtml(record: LocalCaptureRecord) {
  return record.rawPayload?.html || "";
}
