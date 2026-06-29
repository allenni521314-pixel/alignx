import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const distDir = join(scriptDir, "..", "dist");
const indexFile = join(distDir, "index.html");

const routes = [
  "en",
  "en/about",
  "en/privacy-policy",
  "en/terms",
  "en/data-use-policy",
  "en/security",
  "en/contact",
  "zh",
  "zh/about",
  "zh/privacy-policy",
  "zh/terms",
  "zh/data-use-policy",
  "zh/security",
  "zh/contact",
  "login",
  "market-opportunity",
  "product-research",
  "competitor-analysis",
  "business-validation",
  "yesterday-report",
  "today-decisions",
  "prelaunch-check",
  "conversion-diagnosis",
  "traffic-strategy",
  "execution-records",
  "account",
  "admin",
];

if (!existsSync(indexFile)) {
  throw new Error("dist/index.html not found. Run vite build before copying SPA routes.");
}

for (const route of routes) {
  const routeDir = join(distDir, route);
  mkdirSync(routeDir, { recursive: true });
  copyFileSync(indexFile, join(routeDir, "index.html"));
}
