const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });

export default async (request) => {
  const backendBase = process.env.BACKEND_API_URL;

  if (!backendBase) {
    return json(
      {
        detail:
          "Public API backend is not configured. Set BACKEND_API_URL on Netlify to enable live data.",
      },
      503
    );
  }

  const incomingUrl = new URL(request.url);
  const targetPath = incomingUrl.pathname.replace(/^\/api/, "/api");
  const targetUrl = new URL(`${backendBase.replace(/\/$/, "")}${targetPath}${incomingUrl.search}`);
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("content-length");
  headers.set("accept-encoding", "identity");

  let response;
  try {
    response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      redirect: "manual",
    });
  } catch (error) {
    return json(
      {
        detail:
          "Public API backend is temporarily unreachable. Please retry after the backend wakes up.",
        upstream: backendBase,
        error: error instanceof Error ? error.message : "Unknown proxy error",
      },
      502
    );
  }

  const responseHeaders = new Headers(response.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");
  responseHeaders.delete("transfer-encoding");

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  });
};
