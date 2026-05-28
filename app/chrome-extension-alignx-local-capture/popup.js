const ALIGNX_ORIGIN = "https://alignxagent.netlify.app";
const ALIGNX_TARGETS = {
  listing: { path: "/listing-diagnosis", label: "本品诊断" },
  competitor: { path: "/competitor-analysis", label: "竞品诊断" },
  asin: { path: "/asin-manager", label: "ASIN选品" },
};

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
  const pickText = (selectors) => {
    for (const selector of selectors) {
      const node = document.querySelector(selector);
      const text = clean(node?.textContent || node?.getAttribute?.("content") || "");
      if (text) return text;
    }
    return "";
  };
  const parsePrice = (value) => {
    const text = clean(value).replace(/(\d)\s+(\d{2})(\D|$)/, "$1.$2$3");
    if (!text || /list price|was:|save |coupon|monthly|payment plan/i.test(text)) return "";
    const match =
      text.match(/[$€£¥₹]\s*\d{1,4}(?:[,.]\s*\d{2})?/) ||
      text.match(/\b\d{1,4}(?:[,.]\s*\d{2})?\s*(?:USD|EUR|GBP|JPY|CAD|AUD)\b/i);
    return match ? clean(match[0].replace(/\s+/g, "")) : "";
  };
  const pickPrice = () => {
    const selectors = [
      "#corePriceDisplay_desktop_feature_div .priceToPay .a-offscreen",
      "#corePrice_feature_div .priceToPay .a-offscreen",
      "#corePriceDisplay_desktop_feature_div .apexPriceToPay .a-offscreen",
      "#corePrice_feature_div .apexPriceToPay .a-offscreen",
      "#apex_desktop .a-price .a-offscreen",
      "#centerCol .a-price .a-offscreen",
      "#buybox .a-price .a-offscreen",
      "#newBuyBoxPrice",
      "#priceblock_ourprice",
      "#priceblock_dealprice",
      "#priceblock_saleprice",
      "#price_inside_buybox",
      ".priceToPay .a-offscreen",
      ".apexPriceToPay .a-offscreen",
    ];
    for (const selector of selectors) {
      const price = parsePrice(document.querySelector(selector)?.textContent || "");
      if (price) return price;
    }
    for (const blockSelector of ["#corePriceDisplay_desktop_feature_div", "#corePrice_feature_div", "#apex_desktop", "#buybox", "#centerCol"]) {
      const block = document.querySelector(blockSelector);
      if (!block) continue;
      for (const node of block.querySelectorAll(".a-price")) {
        const offscreen = parsePrice(node.querySelector(".a-offscreen")?.textContent || "");
        if (offscreen) return offscreen;
        const symbol = clean(node.querySelector(".a-price-symbol")?.textContent || "$");
        const whole = clean(node.querySelector(".a-price-whole")?.textContent || "");
        const fraction = clean(node.querySelector(".a-price-fraction")?.textContent || "");
        const combined = parsePrice(`${symbol}${whole}${fraction ? `.${fraction}` : ""}`);
        if (combined) return combined;
      }
    }
    return "";
  };
  const pickBullets = () => {
    const selectors = [
      "#feature-bullets li span.a-list-item",
      "#feature-bullets li",
      "#featurebullets_feature_div li span",
      "#featurebullets_feature_div li",
      "#feature-bullets-btf li span",
      "#productFactsDesktop_feature_div li",
      "#productFacts_feature_div li",
      "[data-feature-name='featurebullets'] li span",
    ];
    const seen = new Set();
    const bullets = [];
    for (const selector of selectors) {
      for (const node of document.querySelectorAll(selector)) {
        const text = clean(node.textContent)
          .replace(/^[-•\s]+/, "")
          .replace(/^About this item\s*/i, "");
        if (
          text.length > 8 &&
          text.length < 700 &&
          !/see more|show more|make sure this fits|customer reviews|product information/i.test(text) &&
          !seen.has(text)
        ) {
          seen.add(text);
          bullets.push(text);
        }
        if (bullets.length >= 8) return bullets;
      }
    }
    return bullets;
  };
  const marketplaceFromCurrentHost = (hostname) => {
    const host = String(hostname || "").toLowerCase();
    if (host.includes("amazon.co.uk")) return "UK";
    if (host.includes("amazon.de")) return "DE";
    if (host.includes("amazon.co.jp")) return "JP";
    if (host.includes("amazon.ca")) return "CA";
    if (host.includes("amazon.fr")) return "FR";
    if (host.includes("amazon.it")) return "IT";
    if (host.includes("amazon.es")) return "ES";
    if (host.includes("amazon.com.au")) return "AU";
    return "US";
  };
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
  const bullets = pickBullets();
  const price = pickPrice();
  const rating = pickText(["#acrPopover span.a-icon-alt", "#averageCustomerReviews span.a-icon-alt", "span[data-hook='rating-out-of-text']"]);
  const reviewCount = pickText(["#acrCustomerReviewText", "[data-hook='total-review-count']"]);
  const bsrMatch = safeText.match(/#\s*[\d,]+\s+in\s+[^\n\r]{3,120}/i);
  const bsrRank = bsrMatch ? clean(bsrMatch[0]) : "";
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
    marketplace: marketplaceFromCurrentHost(location.hostname),
    asin: asinMatch ? String(asinMatch[1] || asinMatch[0]).toUpperCase() : "",
    title,
    price,
    rating,
    reviewCount,
    bsrRank,
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
    ["价格", capture.price || "未识别"],
    ["评分", capture.rating || "未识别"],
    ["评论数", capture.reviewCount || "未识别"],
    ["BSR", capture.bsrRank || "未识别"],
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

  const targetKey = document.getElementById("target")?.value || "listing";
  const target = ALIGNX_TARGETS[targetKey] || ALIGNX_TARGETS.listing;
  const capture = { ...alignxLastCapture, destination: targetKey };
  const url = `${ALIGNX_ORIGIN}${target.path}?localCapture=1&asin=${encodeURIComponent(capture.asin || "")}`;
  await chrome.storage.local.set({ alignxPendingCapture: capture });
  const tabs = await chrome.tabs.query({ url: `${ALIGNX_ORIGIN}/*` });
  if (tabs[0]?.id) {
    await chrome.tabs.update(tabs[0].id, { url, active: true });
    if (tabs[0].windowId) await chrome.windows.update(tabs[0].windowId, { focused: true });
  } else {
    await chrome.tabs.create({ url });
  }
  setStatus(`正在发送到 AlignX ${target.label}，会复用已有 AlignX 标签页。`);
}

document.getElementById("capture").addEventListener("click", () => {
  captureCurrentPage().catch((error) => setStatus(error?.message || "采集失败"));
});

document.getElementById("open").addEventListener("click", () => {
  openAlignX().catch((error) => setStatus(error?.message || "打开失败"));
});
