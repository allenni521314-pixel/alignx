import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer, request as httpRequest } from "node:http";
import { extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const distDir = join(__dirname, "dist");
const port = Number(process.env.PORT || 3000);
const apiTarget = new URL(process.env.API_TARGET || "http://127.0.0.1:8000");

const contentTypes = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".json": "application/json; charset=utf-8",
};

function sendFile(res, filePath) {
  const ext = extname(filePath);
  res.writeHead(200, {
    "Content-Type": contentTypes[ext] || "application/octet-stream",
    "Cache-Control": ext === ".html" ? "no-store" : "public, max-age=31536000, immutable",
  });
  createReadStream(filePath).pipe(res);
}

function proxyApi(req, res) {
  const targetPath = req.url || "/";
  const options = {
    protocol: apiTarget.protocol,
    hostname: apiTarget.hostname,
    port: apiTarget.port,
    method: req.method,
    path: targetPath,
    headers: {
      ...req.headers,
      host: apiTarget.host,
    },
  };

  const proxyReq = httpRequest(options, (proxyRes) => {
    res.writeHead(proxyRes.statusCode || 500, proxyRes.headers);
    proxyRes.pipe(res);
  });

  proxyReq.on("error", (err) => {
    res.writeHead(502, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ detail: `API proxy failed: ${err.message}` }));
  });

  req.pipe(proxyReq);
}

const server = createServer((req, res) => {
  const url = req.url || "/";
  if (url.split("?")[0] === "/api/config") {
    res.writeHead(200, {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    });
    res.end(JSON.stringify({ API_BASE_URL: "" }));
    return;
  }

  if (url.startsWith("/api/")) {
    proxyApi(req, res);
    return;
  }

  const pathname = decodeURIComponent(url.split("?")[0] || "/");
  const safePath = normalize(pathname).replace(/^(\.\.[/\\])+/, "");
  let filePath = resolve(distDir, safePath === "/" ? "index.html" : `.${safePath}`);

  if (!filePath.startsWith(resolve(distDir)) || !existsSync(filePath) || statSync(filePath).isDirectory()) {
    filePath = join(distDir, "index.html");
  }

  sendFile(res, filePath);
});

server.listen(port, "127.0.0.1", () => {
  console.log(`AlignX preview server running at http://127.0.0.1:${port}`);
  console.log(`Proxying /api to ${apiTarget.origin}`);
});
