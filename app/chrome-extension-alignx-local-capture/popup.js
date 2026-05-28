const ALIGNX_URL = "https://alignxagent.netlify.app/listing-diagnosis";

function setStatus(message) {
  document.getElementById("status").textContent = message || "";
}

function marketplaceFromHost(hostname) {
  const host = hostname.toLowerCase();
  if (host.includes("amazon.co.uk")) return "UK";
  if (host.includes("amazon.de")) return "DE";
  if (host.includes("amazon.co.jp")) return "JP";
  if (host.includes("amazon.ca")) return "CA";
  if (host.includes("amazon.fr")) return "FR";
  if (host.includes("amazon.it")) return "IT";
  if (host.includes("amazon.es")) return "ES";
  if (host.includes("amazon.com.au")) return "AU";
  return "US";
}

function captureAmazonPage() {
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const url = location.href;
  const safeText = clean(document.body?.innerText || "");
  const asinMatch =
    url.match(/\/(?:dp|gp\/product|product)\/([A-Z0-9]{10})/i) ||
    url.match(/[?&]asin=([A-Z0-9]{10})/i) ||
    safeText.match(/\bB0[A-Z0-9]{8}\b/);
  const urlTitle = decodeURIComponent(url.split("/dp/")[0].split("/").pop() || "").replace(/-/g, " ");
  const title = clean(
    document.querySelector("#productTitle")?.textContent ||
      document.querySelector("[data-automation-id='product-title']")?.textContent ||
      document.querySelector("meta[property='og:title']")?.getAttribute("content") ||
      document.querySelector("meta[name='title']")?.getAttribute("content") ||
      document.querySelector("h1")?.textContent ||
      document.title ||
      urlTitle
  );
  const bullets = Array.from(document.querySelectorAll("#feature-bullets li span, #featurebullets_feature_div li span"))
    .map((node) => clean(node.textContent))
    .filter((text) => text && !/^$/.test(text))
    .slice(0, 8);
  const images = Array.from(document.querySelectorAll("#altImages img, img"))
    .map((img) => img.currentSrc || img.src || "")
    .filter(Boolean)
    .slice(0, 20);
  const clone = document.documentElement.cloneNode(true);
  clone.querySelectorAll("script, style, noscript, iframe, svg").forEach((node) => node.remove());
  const html = `<!doctype html>\n${clone.outerHTML}`;

  return {
    source: "local_browser_capture",
    capturedAt: new Date().toISOString(),
    url,
    hostname: location.hostname,
    marketplace: marketplaceFromHost(location.hostname),
    asin: asinMatch ? String(asinMatch[1] || asinMatch[0]).toUpperCase() : "",
    title,
    bullets,
    imageCount: images.length,
    html,
    text: safeText.slice(0, 20000),
    debug: {
      hasBody: Boolean(document.body),
      titleLength: title.length,
      textLength: safeText.length,
      htmlLength: html.length,
      productTitleFound: Boolean(document.querySelector("#productTitle")),
      h1Found: Boolean(document.querySelector("h1")),
    },
  };
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

function renderCapture(capture) {
  const result = document.getElementById("result");
  result.hidden = false;
  result.replaceChildren();
  [
    ["ASIN", capture.asin || "未识别"],
    ["站点", capture.marketplace || "未识别"],
    ["标题", capture.title || "未识别"],
    ["五点", String(capture.bullets?.length || 0)],
    ["图片", String(capture.imageCount || 0)],
    ["HTML", `${Math.round((capture.html?.length || 0) / 1024)} KB`],
    ["文本", `${Math.round((capture.text?.length || 0) / 1024)} KB`],
  ].forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "row";
    const key = document.createElement("span");
    key.className = "key";
    key.textContent = label;
    const val = document.createElement("span");
    val.className = "val";
    val.textContent = value;
    row.append(key, val);
    result.append(row);
  });
}

async function captureCurrentPage() {
  setStatus("正在读取当前页面...");
  const tab = await getActiveTab();
  if (!tab?.url || !/amazon\./i.test(tab.url)) {
    setStatus("请先切换到 Amazon 商品详情页，再点击采集。");
    return;
  }

  const [result] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: captureAmazonPage,
  });
  const capture = result?.result;
  if (!capture?.html || (!capture?.asin && !/\/(?:dp|gp\/product|product)\//i.test(capture?.url || ""))) {
    const debug = capture?.debug ? ` 调试：${JSON.stringify(capture.debug)}` : "";
    setStatus(`未读取到有效商品页内容，请确认当前页面是 Amazon 商品详情页。${debug}`);
    return;
  }

  await chrome.storage.local.set({ alignxLastCapture: capture });
  renderCapture(capture);
  setStatus("已采集到本地页面。下一步点击“打开 AlignX 本品诊断”，插件会把采集结果交给 AlignX。");
}

async function openAlignX() {
  const { alignxLastCapture } = await chrome.storage.local.get("alignxLastCapture");
  if (!alignxLastCapture) {
    setStatus("还没有采集结果，请先在 Amazon 商品页点击采集。");
    return;
  }

  const tab = await chrome.tabs.create({ url: `${ALIGNX_URL}?localCapture=1&asin=${encodeURIComponent(alignxLastCapture.asin || "")}` });
  setStatus("正在打开 AlignX...");
  const listener = async (tabId, changeInfo) => {
    if (tabId !== tab.id || changeInfo.status !== "complete") return;
    chrome.tabs.onUpdated.removeListener(listener);
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      args: [alignxLastCapture],
      func: (capture) => {
        localStorage.setItem("alignx_local_browser_capture", JSON.stringify(capture));
        window.dispatchEvent(new Event("alignx-local-browser-capture"));
      },
    });
  };
  chrome.tabs.onUpdated.addListener(listener);
}

document.getElementById("capture").addEventListener("click", () => {
  captureCurrentPage().catch((error) => setStatus(error?.message || "采集失败"));
});

document.getElementById("open").addEventListener("click", () => {
  openAlignX().catch((error) => setStatus(error?.message || "打开失败"));
});
